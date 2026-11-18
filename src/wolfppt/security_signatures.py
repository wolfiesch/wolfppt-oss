"""Part of ``security``; split out verbatim to keep modules reviewable.

Signatures follow the layout Office writes and verifies: ECMA-376 Part 2
section 13 package signatures with the [MS-OFFCRYPTO] 2.5 Office object and a
XAdES-EPES ``SignedProperties`` reference, inclusive C14N throughout, and a
manifest limited to the parts and relationships Office signs.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import io
import os
import posixpath
import zipfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .package_limits import (
    PPTX_PACKAGE_LIMITS as PPTX_SECURITY_LIMITS,
)
from .package_limits import (
    _zip_envelope_refusal,
)
from .render_package import Package, resolve_target
from .security import (
    _CT_NS,
    _DS_NS,
    _DS_OBJECT_TYPE,
    _INCLUSIVE_C14N,
    _OFFICE_DIGSIG_NS,
    _PACKAGE_DIGSIG_NS,
    _REFUSED,
    _REL_NS,
    _RELATIONSHIP_TRANSFORM,
    _RSA_SHA256,
    _SHA256_DIGEST,
    _SIGNATURE_CONTENT_TYPE,
    _SIGNATURE_ORIGIN_CONTENT_TYPE,
    _SIGNATURE_ORIGIN_PART,
    _SIGNATURE_ORIGIN_REL,
    _SIGNATURE_ORIGIN_RELS,
    _SIGNATURE_PART,
    _SIGNATURE_PREFIX,
    _SIGNATURE_REL,
    _XADES_NS,
    _XADES_SIGNED_PROPERTIES_TYPE,
    PptxDigitalSignature,
    PptxSignatureInspectionReport,
    PptxSignatureInspectionRequest,
    PptxSignatureReport,
    PptxSignatureRequest,
    _admitted_package,
)

_XML_NS = "http://www.w3.org/XML/1998/namespace"
_SIGNATURE_ID = "idPackageSignature"
_PACKAGE_OBJECT_ID = "idPackageObject"
_OFFICE_OBJECT_ID = "idOfficeObject"
_SIGNED_PROPERTIES_ID = "idSignedProperties"
_SIGNATURE_TIME_FORMAT = "YYYY-MM-DDThh:mm:ssTZD"

# Relationship types whose targets Office signs, keyed by the type suffix after
# ``/relationships/``. ECMA-376 Part 2 section 13.2.4.16 leaves the selection to
# the producer; this is the Office 2010+ set (also used by Apache POI's
# OOXMLSignatureFacet). Core and extended properties, thumbnails and the
# signature origin are left unsigned, exactly as PowerPoint leaves them.
_SIGNED_RELATIONSHIP_KINDS = frozenset(
    {
        "activeXControlBinary", "aFChunk", "attachedTemplate",
        "attachedToolbars", "audio", "calcChain", "chart", "chartColorStyle",
        "chartLayout", "chartsheet", "chartStyle", "chartUserShapes",
        "commentAuthors", "comments", "connections", "connectorXml", "control",
        "ctrlProp", "customData", "customProperty", "customXml", "diagram",
        "diagramColors", "diagramColorsHeader", "diagramData", "diagramDrawing",
        "diagramLayout", "diagramLayoutHeader", "diagramQuickStyle",
        "diagramQuickStyleHeader", "dialogsheet", "dictionary", "documentParts",
        "downRev", "drawing", "endnotes", "externalLink", "externalLinkPath",
        "font", "fontTable", "footer", "footnotes", "functionPrototypes",
        "glossaryDocument", "graphicFrameDoc", "groupShapeXml", "handoutMaster",
        "hdphoto", "header", "hyperlink", "image", "ink", "inkXml",
        "keyMapCustomizations", "legacyDiagramText", "legacyDocTextInfo",
        "mailMergeHeaderSource", "mailMergeRecipientData", "mailMergeSource",
        "media", "notesMaster", "notesSlide", "numbering", "officeDocument",
        "oleObject", "package", "pictureXml", "pivotCacheDefinition",
        "pivotCacheRecords", "pivotTable", "powerPivotData", "presProps",
        "printerSettings", "queryTable", "recipientData", "settings", "shapeXml",
        "sharedStrings", "sheetMetadata", "slicer", "slicerCache", "slide",
        "slideLayout", "slideMaster", "slideUpdateInfo", "slideUpdateUrl",
        "smartTags", "styles", "stylesWithEffects", "table", "tableSingleCells",
        "tableStyles", "tags", "theme", "themeOverride", "timeline",
        "timelineCache", "transform", "ui/altText", "ui/buttonSize",
        "ui/controlID", "ui/description", "ui/enabled", "ui/extensibility",
        "ui/helperText", "ui/imageID", "ui/imageMso", "ui/keyTip", "ui/label",
        "ui/lcid", "ui/loud", "ui/pressed", "ui/progID", "ui/ribbonID",
        "ui/showImage", "ui/showLabel", "ui/supertip", "ui/target", "ui/text",
        "ui/title", "ui/tooltip", "ui/userCustomization", "ui/visible",
        "userXmlData", "vbaProject", "video", "viewProps", "vmlDrawing",
        "volatileDependencies", "webSettings", "wordVbaData", "worksheet",
        "wsSortMap", "xlBinaryIndex", "xlExternalLinkPath/xlAlternateStartup",
        "xlExternalLinkPath/xlLibrary", "xlExternalLinkPath/xlPathMissing",
        "xlExternalLinkPath/xlStartup", "xlIntlMacrosheet", "xlMacrosheet",
    }
)  # fmt: skip
_SIGNED_CUSTOM_XML_CONTENT_TYPES = frozenset({"inkml+xml", "text/xml"})

# [MS-OFFCRYPTO] 2.5.2.5 SignatureInfoV1: every element is required, in this
# order. The environment fields describe the nominal Office 16 platform the
# signature targets, as interoperable producers write them.
_SIGNATURE_INFO_V1 = (
    ("SetupID", None),
    ("SignatureText", None),
    ("SignatureImage", None),
    ("SignatureComments", None),
    ("WindowsVersion", "10.0"),
    ("OfficeVersion", "16.0"),
    ("ApplicationVersion", "16.0"),
    ("Monitors", "1"),
    ("HorizontalResolution", "1024"),
    ("VerticalResolution", "768"),
    ("ColorDepth", "32"),
    ("SignatureProviderId", "{00000000-0000-0000-0000-000000000000}"),
    ("SignatureProviderUrl", None),
    ("SignatureProviderDetails", "9"),
    ("SignatureType", "1"),
)


def _signature_refusal(
    request: PptxSignatureRequest, code: str, recovery: str | None = None
) -> PptxSignatureReport:
    return PptxSignatureReport(
        status=_REFUSED,
        code=code,
        source_sha256=request.source_sha256,
        destination_sha256=None,
        signer=None,
        recovery=recovery,
    )


def _signature_inspection_refusal(
    request: PptxSignatureInspectionRequest, code: str, recovery: str | None = None
) -> PptxSignatureInspectionReport:
    return PptxSignatureInspectionReport(
        status=_REFUSED,
        code=code,
        source_sha256=request.source_sha256,
        signatures=(),
        recovery=recovery,
    )


def _signature_snapshot(
    source: Path, expected_sha256: str
) -> tuple[bytes, Package] | str:
    try:
        with source.open("rb") as stream:
            payload = stream.read(PPTX_SECURITY_LIMITS.max_archive_size + 1)
    except OSError:
        return "source_unreadable"
    if len(payload) > PPTX_SECURITY_LIMITS.max_archive_size:
        return "source_size_limit"
    envelope = _zip_envelope_refusal(payload, PPTX_SECURITY_LIMITS)
    if envelope is not None:
        return f"source_{envelope.code}"
    admitted = _admitted_package("signature", source, payload, expected_sha256)
    if isinstance(admitted, str):
        return admitted.removeprefix("signature_")
    return payload, admitted


def _xml_root(payload: bytes) -> ET.Element:
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("xml_declaration_unsupported")
    return ET.fromstring(payload)


def _lxml_root(payload: bytes, etree: Any) -> Any:
    """Parse package XML with lxml, keeping the author's namespace prefixes."""
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("xml_declaration_unsupported")
    return etree.fromstring(
        payload,
        etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            load_dtd=False,
            remove_blank_text=False,
        ),
    )


def _canonical_xml(element: Any) -> bytes:
    """Return inclusive C14N 1.0 of ``element`` as an XMLDSIG document subset.

    libxml2's subtree canonicalization emits ``xmlns=""`` on descendants when
    the apex inherits a default namespace, which breaks every same-document
    reference Office writes. Canonicalize a standalone copy instead whose apex
    carries every in-scope namespace and inherited ``xml:*`` attribute, which
    is exactly what C14N renders on a document-subset apex.
    """
    dependency = _signature_dependency()
    if dependency is None:
        raise ValueError("signature_dependency_missing")
    etree = dependency[5]
    if element.getparent() is None:
        return etree.tostring(element, method="c14n", with_comments=False)
    apex = etree.Element(element.tag, attrib=dict(element.attrib), nsmap=element.nsmap)
    for ancestor in element.iterancestors():
        for name, value in ancestor.attrib.items():
            if name.startswith(f"{{{_XML_NS}}}") and name not in apex.attrib:
                apex.set(name, value)
    apex.text = element.text
    for child in element:
        apex.append(copy.deepcopy(child))
    return etree.tostring(apex, method="c14n", exclusive=False, with_comments=False)


def _signature_part_marker(parts: Mapping[str, bytes]) -> bool:
    if any(name.casefold().startswith(_SIGNATURE_PREFIX) for name in parts):
        return True
    try:
        content_types = _xml_root(parts["[Content_Types].xml"])
        root_rels = _xml_root(parts["_rels/.rels"])
    except (KeyError, ET.ParseError, ValueError):
        return True
    if any(
        child.attrib.get("ContentType")
        in {_SIGNATURE_ORIGIN_CONTENT_TYPE, _SIGNATURE_CONTENT_TYPE}
        for child in content_types
    ):
        return True
    return any(child.attrib.get("Type") == _SIGNATURE_ORIGIN_REL for child in root_rels)


def _next_relationship_id(root: Any) -> str:
    used = {child.attrib.get("Id") for child in root}
    index = 1
    while f"rId{index}" in used:
        index += 1
    return f"rId{index}"


def _signature_content_types(parts: Mapping[str, bytes], etree: Any) -> bytes:
    """Register the origin by ``sigs`` extension and the signature by override."""
    root = _lxml_root(parts["[Content_Types].xml"], etree)
    if root.tag != f"{{{_CT_NS}}}Types":
        raise ValueError("content_types_malformed")
    overrides = {
        child.attrib.get("PartName", "")
        for child in root
        if child.tag == f"{{{_CT_NS}}}Override"
    }
    if f"/{_SIGNATURE_ORIGIN_PART}" in overrides or f"/{_SIGNATURE_PART}" in overrides:
        raise ValueError("signature_content_type_present")
    defaults = [child for child in root if child.tag == f"{{{_CT_NS}}}Default"]
    origin_extension = _SIGNATURE_ORIGIN_PART.rsplit(".", 1)[-1]
    declared = [
        child
        for child in defaults
        if child.attrib.get("Extension", "").casefold() == origin_extension
    ]
    if any(
        child.attrib.get("ContentType") != _SIGNATURE_ORIGIN_CONTENT_TYPE
        for child in declared
    ):
        raise ValueError("signature_content_type_present")
    if not declared:
        default = etree.Element(
            f"{{{_CT_NS}}}Default",
            Extension=origin_extension,
            ContentType=_SIGNATURE_ORIGIN_CONTENT_TYPE,
        )
        if defaults:
            defaults[-1].addnext(default)
        else:
            root.insert(0, default)
        default.tail = defaults[-1].tail if defaults else None
    etree.SubElement(
        root,
        f"{{{_CT_NS}}}Override",
        PartName=f"/{_SIGNATURE_PART}",
        ContentType=_SIGNATURE_CONTENT_TYPE,
    )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _signature_root_relationships(parts: Mapping[str, bytes], etree: Any) -> bytes:
    root = _lxml_root(parts["_rels/.rels"], etree)
    if root.tag != f"{{{_REL_NS}}}Relationships":
        raise ValueError("root_relationships_malformed")
    if any(child.attrib.get("Type") == _SIGNATURE_ORIGIN_REL for child in root):
        raise ValueError("signature_origin_relationship_present")
    etree.SubElement(
        root,
        f"{{{_REL_NS}}}Relationship",
        Id=_next_relationship_id(root),
        Type=_SIGNATURE_ORIGIN_REL,
        Target=_SIGNATURE_ORIGIN_PART,
    )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _signature_dependency() -> tuple[Any, Any, Any, Any, Any, Any] | None:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from lxml import etree
    except ImportError:
        return None
    return x509, hashes, serialization, padding, rsa, etree


def _load_signature_credentials(
    request: PptxSignatureRequest, dependency: tuple[Any, Any, Any, Any, Any, Any]
) -> tuple[Any, Any, str] | str:
    x509, hashes, serialization, padding, rsa, _ = dependency
    try:
        certificate_bytes = request.certificate.read_bytes()
        private_key_bytes = request.private_key.read_bytes()
    except OSError:
        return "credentials_unreadable"
    password: bytes | None = None
    if request.private_key_password_env is not None:
        secret = os.environ.get(request.private_key_password_env)
        if secret is None:
            return "private_key_password_missing"
        if not secret:
            return "private_key_password_blank"
        password = secret.encode("utf-8")
    try:
        try:
            certificate = x509.load_pem_x509_certificate(certificate_bytes)
        except ValueError:
            certificate = x509.load_der_x509_certificate(certificate_bytes)
        try:
            key = serialization.load_pem_private_key(private_key_bytes, password)
        except ValueError:
            key = serialization.load_der_private_key(private_key_bytes, password)
    except (TypeError, ValueError):
        return "credentials_invalid"
    if not isinstance(key, rsa.RSAPrivateKey) or not isinstance(
        certificate.public_key(), rsa.RSAPublicKey
    ):
        return "credentials_algorithm_unsupported"
    from cryptography.exceptions import InvalidSignature

    probe = b"wolfppt-opc-signature-key-match"
    try:
        signature = key.sign(probe, padding.PKCS1v15(), hashes.SHA256())
        certificate.public_key().verify(
            signature, probe, padding.PKCS1v15(), hashes.SHA256()
        )
    except (InvalidSignature, TypeError, ValueError):
        return "credentials_key_mismatch"
    return certificate, key, certificate.subject.rfc4514_string()


def _reference_uri(part: str, content_type: str) -> str:
    """Return the OPC part reference URI; Office writes the content type raw."""
    return f"/{part}?ContentType={content_type}"


def _relationship_source(part: str) -> str | None:
    """Return the source part of a relationship part, or None for other parts."""
    parent, filename = posixpath.split(part)
    if posixpath.basename(parent) != "_rels" or not filename.endswith(".rels"):
        return None
    return posixpath.join(posixpath.dirname(parent), filename[: -len(".rels")])


def _signed_relationship(relationship_type: str) -> bool:
    _, marker, kind = relationship_type.rpartition("/relationships/")
    return bool(marker) and (
        kind in _SIGNED_RELATIONSHIP_KINDS or kind.endswith("customXml")
    )


def _office_manifest(
    parts: Mapping[str, bytes], content_type: Callable[[str], str | None]
) -> dict[str, tuple[str, ...] | None]:
    """Return the parts Office signs, mapped to their signed relationship Ids.

    Relationship parts map to the Ids their RelationshipTransform selects; other
    parts map to None and are digested as raw bytes. Only internal targets of
    signed relationship types are included, each once.
    """
    manifest: dict[str, tuple[str, ...] | None] = {}
    visited: set[str] = set()
    for rels_part in sorted(parts):
        source = _relationship_source(rels_part)
        if source is None or rels_part.startswith(_SIGNATURE_PREFIX):
            continue
        root = _xml_root(parts[rels_part])
        if root.tag != f"{{{_REL_NS}}}Relationships":
            raise ValueError("relationships_malformed")
        source_ids: list[str] = []
        for relationship in root.findall(f"{{{_REL_NS}}}Relationship"):
            identifier = relationship.attrib.get("Id")
            kind = relationship.attrib.get("Type")
            target = relationship.attrib.get("Target")
            if not identifier or not kind or target is None:
                raise ValueError("relationships_malformed")
            if relationship.attrib.get(
                "TargetMode"
            ) == "External" or not _signed_relationship(kind):
                continue
            source_ids.append(identifier)
            member = resolve_target(source, target)
            if member in visited:
                continue
            visited.add(member)
            if member not in parts or member.startswith(_SIGNATURE_PREFIX):
                raise ValueError("signed_relationship_target_missing")
            if kind.endswith("customXml") and (
                content_type(member) not in _SIGNED_CUSTOM_XML_CONTENT_TYPES
            ):
                continue
            manifest[member] = None
        if source_ids:
            manifest[rels_part] = tuple(source_ids)
    return manifest


def _relationship_transform(
    payload: bytes, source_ids: frozenset[str], etree: Any
) -> bytes:
    """Apply the ECMA-376 Part 2 13.2.4.24 transform, then inclusive C14N."""
    source = _lxml_root(payload, etree)
    if source.tag != f"{{{_REL_NS}}}Relationships":
        raise ValueError("relationships_malformed")
    selected = [
        child
        for child in source
        if child.tag == f"{{{_REL_NS}}}Relationship"
        and child.attrib.get("Id") in source_ids
    ]
    root = etree.Element(f"{{{_REL_NS}}}Relationships", nsmap={None: _REL_NS})
    for relationship in sorted(selected, key=lambda child: child.attrib["Id"]):
        attributes = {
            name: relationship.attrib[name]
            for name in ("Id", "Target", "TargetMode", "Type")
            if name in relationship.attrib
        }
        attributes.setdefault("TargetMode", "Internal")
        etree.SubElement(root, f"{{{_REL_NS}}}Relationship", attributes)
    return _canonical_xml(root)


def _add_digest_reference(
    parent: Any,
    uri: str,
    payload: bytes,
    *,
    reference_type: str | None = None,
    transforms: tuple[str, ...] = (),
) -> Any:
    dependency = _signature_dependency()
    if dependency is None:
        raise ValueError("signature_dependency_missing")
    etree = dependency[5]
    reference = etree.SubElement(parent, f"{{{_DS_NS}}}Reference")
    if reference_type is not None:
        reference.set("Type", reference_type)
    reference.set("URI", uri)
    if transforms:
        container = etree.SubElement(reference, f"{{{_DS_NS}}}Transforms")
        for algorithm in transforms:
            etree.SubElement(container, f"{{{_DS_NS}}}Transform", Algorithm=algorithm)
    etree.SubElement(reference, f"{{{_DS_NS}}}DigestMethod", Algorithm=_SHA256_DIGEST)
    etree.SubElement(reference, f"{{{_DS_NS}}}DigestValue").text = base64.b64encode(
        hashlib.sha256(payload).digest()
    ).decode("ascii")
    return reference


def _add_manifest(
    package_object: Any,
    parts: Mapping[str, bytes],
    content_type: Callable[[str], str | None],
    etree: Any,
) -> None:
    manifest = etree.SubElement(package_object, f"{{{_DS_NS}}}Manifest")
    entries = []
    for member, source_ids in _office_manifest(parts, content_type).items():
        member_type = content_type(member)
        if member_type is None:
            raise ValueError("signature_content_type_missing")
        entries.append((_reference_uri(member, member_type), member, source_ids))
    # PowerPoint orders manifest references by URI, ignoring case.
    for uri, member, source_ids in sorted(entries, key=lambda entry: entry[0].lower()):
        if source_ids is None:
            _add_digest_reference(manifest, uri, parts[member])
            continue
        reference = _add_digest_reference(
            manifest,
            uri,
            _relationship_transform(parts[member], frozenset(source_ids), etree),
            transforms=(_RELATIONSHIP_TRANSFORM, _INCLUSIVE_C14N),
        )
        relationship_transform = reference.find(
            f"{{{_DS_NS}}}Transforms/{{{_DS_NS}}}Transform"
        )
        for identifier in source_ids:
            etree.SubElement(
                relationship_transform,
                f"{{{_PACKAGE_DIGSIG_NS}}}RelationshipReference",
                nsmap={"mdssi": _PACKAGE_DIGSIG_NS},
                SourceId=identifier,
            )


def _x509_issuer_name(certificate: Any) -> str:
    """Return the issuer as Windows renders it: most specific RDN first."""
    return ", ".join(rdn.rfc4514_string() for rdn in reversed(certificate.issuer.rdns))


def _signature_xml(
    parts: Mapping[str, bytes],
    package: Package,
    certificate: Any,
    key: Any,
    dependency: tuple[Any, Any, Any, Any, Any, Any],
) -> bytes:
    _, hashes, serialization, padding, _, etree = dependency
    signed_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    certificate_der = certificate.public_bytes(serialization.Encoding.DER)

    def element(parent: Any, name: str, text: str | None = None, **attrs: str) -> Any:
        child = etree.SubElement(parent, f"{{{_DS_NS}}}{name}", attrs)
        child.text = text
        return child

    signature = etree.Element(
        f"{{{_DS_NS}}}Signature", Id=_SIGNATURE_ID, nsmap={None: _DS_NS}
    )
    signed_info = element(signature, "SignedInfo")
    element(signed_info, "CanonicalizationMethod", Algorithm=_INCLUSIVE_C14N)
    element(signed_info, "SignatureMethod", Algorithm=_RSA_SHA256)
    signature_value = element(signature, "SignatureValue")
    element(
        element(element(signature, "KeyInfo"), "X509Data"),
        "X509Certificate",
        base64.b64encode(certificate_der).decode("ascii"),
    )

    package_object = element(signature, "Object", Id=_PACKAGE_OBJECT_ID)
    _add_manifest(package_object, parts, package.content_type, etree)
    time_property = element(
        element(package_object, "SignatureProperties"),
        "SignatureProperty",
        Id="idSignatureTime",
        Target=f"#{_SIGNATURE_ID}",
    )
    signature_time = etree.SubElement(
        time_property,
        f"{{{_PACKAGE_DIGSIG_NS}}}SignatureTime",
        nsmap={"mdssi": _PACKAGE_DIGSIG_NS},
    )
    etree.SubElement(
        signature_time, f"{{{_PACKAGE_DIGSIG_NS}}}Format"
    ).text = _SIGNATURE_TIME_FORMAT
    etree.SubElement(signature_time, f"{{{_PACKAGE_DIGSIG_NS}}}Value").text = signed_at

    office_object = element(signature, "Object", Id=_OFFICE_OBJECT_ID)
    office_property = element(
        element(office_object, "SignatureProperties"),
        "SignatureProperty",
        Id="idOfficeV1Details",
        Target=f"#{_SIGNATURE_ID}",
    )
    details = etree.SubElement(
        office_property,
        f"{{{_OFFICE_DIGSIG_NS}}}SignatureInfoV1",
        nsmap={None: _OFFICE_DIGSIG_NS},
    )
    for name, value in _SIGNATURE_INFO_V1:
        etree.SubElement(details, f"{{{_OFFICE_DIGSIG_NS}}}{name}").text = value

    qualifying = etree.SubElement(
        element(signature, "Object"),
        f"{{{_XADES_NS}}}QualifyingProperties",
        nsmap={"xd": _XADES_NS},
        Target=f"#{_SIGNATURE_ID}",
    )
    signed_properties = etree.SubElement(
        qualifying, f"{{{_XADES_NS}}}SignedProperties", Id=_SIGNED_PROPERTIES_ID
    )
    signature_properties = etree.SubElement(
        signed_properties, f"{{{_XADES_NS}}}SignedSignatureProperties"
    )
    etree.SubElement(
        signature_properties, f"{{{_XADES_NS}}}SigningTime"
    ).text = signed_at
    signing_certificate = etree.SubElement(
        signature_properties, f"{{{_XADES_NS}}}SigningCertificate"
    )
    cert = etree.SubElement(signing_certificate, f"{{{_XADES_NS}}}Cert")
    cert_digest = etree.SubElement(cert, f"{{{_XADES_NS}}}CertDigest")
    element(cert_digest, "DigestMethod", Algorithm=_SHA256_DIGEST)
    element(
        cert_digest,
        "DigestValue",
        base64.b64encode(hashlib.sha256(certificate_der).digest()).decode("ascii"),
    )
    issuer_serial = etree.SubElement(cert, f"{{{_XADES_NS}}}IssuerSerial")
    element(issuer_serial, "X509IssuerName", _x509_issuer_name(certificate))
    element(issuer_serial, "X509SerialNumber", str(certificate.serial_number))
    etree.SubElement(
        etree.SubElement(
            signature_properties, f"{{{_XADES_NS}}}SignaturePolicyIdentifier"
        ),
        f"{{{_XADES_NS}}}SignaturePolicyImplied",
    )

    for identifier, target in (
        (_PACKAGE_OBJECT_ID, package_object),
        (_OFFICE_OBJECT_ID, office_object),
    ):
        _add_digest_reference(
            signed_info,
            f"#{identifier}",
            _canonical_xml(target),
            reference_type=_DS_OBJECT_TYPE,
        )
    _add_digest_reference(
        signed_info,
        f"#{_SIGNED_PROPERTIES_ID}",
        _canonical_xml(signed_properties),
        reference_type=_XADES_SIGNED_PROPERTIES_TYPE,
        transforms=(_INCLUSIVE_C14N,),
    )
    signature_value.text = base64.b64encode(
        key.sign(_canonical_xml(signed_info), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    return b'<?xml version="1.0" encoding="UTF-8"?>' + etree.tostring(
        signature, encoding="UTF-8"
    )


def _signature_archive(
    snapshot: bytes,
    package: Package,
    certificate: Any,
    key: Any,
    dependency: tuple[Any, Any, Any, Any, Any, Any],
) -> bytes:
    etree = dependency[5]
    with zipfile.ZipFile(io.BytesIO(snapshot)) as archive:
        infos = archive.infolist()
        parts = {
            info.filename: archive.read(info) for info in infos if not info.is_dir()
        }
    parts["[Content_Types].xml"] = _signature_content_types(parts, etree)
    parts["_rels/.rels"] = _signature_root_relationships(parts, etree)
    # The origin part has no content (ECMA-376 Part 2 13.2.4.1), as Office writes it.
    parts[_SIGNATURE_ORIGIN_PART] = b""
    parts[_SIGNATURE_ORIGIN_RELS] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        b'relationships"><Relationship Id="rId1" Type="'
        + _SIGNATURE_REL.encode("ascii")
        + b'" Target="sig1.xml"/></Relationships>'
    )
    parts[_SIGNATURE_PART] = _signature_xml(
        parts, package, certificate, key, dependency
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as rewritten:
        known = set()
        for info in infos:
            if info.is_dir() or info.filename not in parts:
                continue
            copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            copied.compress_type = info.compress_type
            copied.comment = info.comment
            copied.external_attr = info.external_attr
            copied.create_system = info.create_system
            rewritten.writestr(copied, parts[info.filename])
            known.add(info.filename)
        for name in sorted(set(parts) - known):
            rewritten.writestr(name, parts[name], compress_type=zipfile.ZIP_DEFLATED)
    return output.getvalue()


def _signature_candidates(parts: Mapping[str, bytes]) -> tuple[str, ...]:
    return tuple(
        sorted(
            part
            for part in parts
            if part.startswith(_SIGNATURE_PREFIX)
            and part.casefold().endswith(".xml")
            and part != _SIGNATURE_ORIGIN_RELS
        )
    )


def _registered_signature_parts(
    parts: Mapping[str, bytes], candidates: tuple[str, ...], package: Package
) -> tuple[str, ...] | str:
    """Return exactly the signature XML parts registered by OPC relationships."""

    try:
        content_types = _xml_root(parts["[Content_Types].xml"])
        root_relationships = _xml_root(parts["_rels/.rels"])
        origin_relationships = _xml_root(parts[_SIGNATURE_ORIGIN_RELS])
    except (KeyError, ET.ParseError, ValueError):
        return "registry_malformed"
    if (
        content_types.tag != f"{{{_CT_NS}}}Types"
        or root_relationships.tag != f"{{{_REL_NS}}}Relationships"
        or origin_relationships.tag != f"{{{_REL_NS}}}Relationships"
    ):
        return "registry_malformed"

    def declared(part: str, content_type: str) -> bool:
        """The part resolves to one content type, by extension or by override."""
        overrides = [
            child
            for child in content_types.findall(f"{{{_CT_NS}}}Override")
            if child.attrib.get("PartName") == f"/{part}"
        ]
        return len(overrides) <= 1 and package.content_type(part) == content_type

    origin_links = [
        child
        for child in root_relationships.findall(f"{{{_REL_NS}}}Relationship")
        if child.attrib.get("Type") == _SIGNATURE_ORIGIN_REL
    ]
    if (
        len(origin_links) != 1
        or origin_links[0].attrib.get("TargetMode") == "External"
        or origin_links[0].attrib.get("Target", "").lstrip("/")
        != _SIGNATURE_ORIGIN_PART
        or not declared(_SIGNATURE_ORIGIN_PART, _SIGNATURE_ORIGIN_CONTENT_TYPE)
    ):
        return "registry_malformed"

    registered: list[str] = []
    for relationship in origin_relationships.findall(f"{{{_REL_NS}}}Relationship"):
        if relationship.attrib.get("Type") != _SIGNATURE_REL:
            continue
        target = relationship.attrib.get("Target")
        if (
            target is None
            or relationship.attrib.get("TargetMode") == "External"
            or target.startswith("/")
            or any(component in {"", ".", ".."} for component in target.split("/"))
        ):
            return "registry_malformed"
        registered.append(f"{_SIGNATURE_PREFIX}{target}")
    if (
        not registered
        or len(set(registered)) != len(registered)
        or set(registered) != set(candidates)
        or any(not declared(part, _SIGNATURE_CONTENT_TYPE) for part in registered)
    ):
        return "registry_malformed"
    return tuple(sorted(registered))


def _base64_value(text: str) -> bytes:
    """Decode an XML Schema base64Binary value; Office wraps it across lines."""
    return base64.b64decode("".join(text.split()), validate=True)


def _reference_digest_code(reference: Any, payload: bytes) -> str | None:
    methods = reference.findall(f"{{{_DS_NS}}}DigestMethod")
    values = reference.findall(f"{{{_DS_NS}}}DigestValue")
    if len(methods) != 1 or len(values) != 1 or values[0].text is None:
        return "digest_malformed"
    if methods[0].attrib.get("Algorithm") != _SHA256_DIGEST:
        return "algorithm_unsupported"
    try:
        expected = _base64_value(values[0].text)
    except (binascii.Error, ValueError):
        return "digest_malformed"
    if len(expected) != hashlib.sha256().digest_size:
        return "digest_malformed"
    if expected != hashlib.sha256(payload).digest():
        return "digest_mismatch"
    return None


def _reference_transforms(reference: Any) -> list[Any] | None:
    """Return a reference's Transform elements, or None when malformed."""
    containers = reference.findall(f"{{{_DS_NS}}}Transforms")
    if len(containers) > 1:
        return None
    if not containers:
        return []
    transforms = list(containers[0])
    if not transforms or any(
        transform.tag != f"{{{_DS_NS}}}Transform" for transform in transforms
    ):
        return None
    return transforms


def _relationship_source_ids(transform: Any) -> frozenset[str] | None:
    """Return the SourceId selection of a RelationshipTransform element."""
    identifiers: list[str] = []
    for child in transform:
        identifier = child.attrib.get("SourceId")
        if child.tag != f"{{{_PACKAGE_DIGSIG_NS}}}RelationshipReference" or not (
            identifier
        ):
            return None
        identifiers.append(identifier)
    return frozenset(identifiers) if identifiers else None


def _signature_from_payload(
    part: str, payload: bytes, parts: Mapping[str, bytes], package: Package
) -> PptxDigitalSignature:
    dependency = _signature_dependency()
    if dependency is None:
        return PptxDigitalSignature(part, None, None, None, "dependency_missing")
    x509, hashes, _, padding, rsa, etree = dependency
    try:
        root = _lxml_root(payload, etree)
    except (etree.XMLSyntaxError, ValueError):
        return PptxDigitalSignature(part, None, None, None, "signature_malformed")
    if root.tag != f"{{{_DS_NS}}}Signature":
        return PptxDigitalSignature(part, None, None, None, "signature_malformed")
    certificate_nodes = root.findall(
        f"{{{_DS_NS}}}KeyInfo/{{{_DS_NS}}}X509Data/{{{_DS_NS}}}X509Certificate"
    )
    timestamp_node = root.find(
        f".//{{{_PACKAGE_DIGSIG_NS}}}SignatureTime/{{{_PACKAGE_DIGSIG_NS}}}Value"
    )
    timestamp = timestamp_node.text if timestamp_node is not None else None
    signer = None
    try:
        if len(certificate_nodes) != 1 or not certificate_nodes[0].text:
            raise ValueError
        certificate = x509.load_der_x509_certificate(
            _base64_value(certificate_nodes[0].text)
        )
        signer = certificate.subject.rfc4514_string()
    except (binascii.Error, TypeError, ValueError):
        return PptxDigitalSignature(
            part, signer, timestamp, None, "certificate_invalid"
        )

    def verdict(code: str) -> PptxDigitalSignature:
        valid = False if code in {"digest_mismatch", "signature_invalid"} else None
        return PptxDigitalSignature(part, signer, timestamp, valid, code)

    signed_infos = root.findall(f"{{{_DS_NS}}}SignedInfo")
    signature_values = root.findall(f"{{{_DS_NS}}}SignatureValue")
    if (
        len(signed_infos) != 1
        or len(signature_values) != 1
        or not signature_values[0].text
    ):
        return verdict("signature_malformed")
    signed_info = signed_infos[0]
    canonicalizations = signed_info.findall(f"{{{_DS_NS}}}CanonicalizationMethod")
    signature_methods = signed_info.findall(f"{{{_DS_NS}}}SignatureMethod")
    if len(canonicalizations) != 1 or len(signature_methods) != 1:
        return verdict("signature_malformed")
    if (
        canonicalizations[0].attrib.get("Algorithm") != _INCLUSIVE_C14N
        or signature_methods[0].attrib.get("Algorithm") != _RSA_SHA256
        or not isinstance(certificate.public_key(), rsa.RSAPublicKey)
    ):
        return verdict("algorithm_unsupported")

    from cryptography.exceptions import InvalidSignature

    try:
        certificate.public_key().verify(
            _base64_value(signature_values[0].text),
            _canonical_xml(signed_info),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (binascii.Error, InvalidSignature, TypeError, ValueError):
        return verdict("signature_invalid")

    identified: dict[str, Any] = {}
    for node in root.iter():
        identifier = node.attrib.get("Id") if isinstance(node.tag, str) else None
        if identifier is None:
            continue
        if identifier in identified:
            return verdict("signed_info_invalid")
        identified[identifier] = node
    # Each signed same-document target: its element, reference Type, and whether
    # it must be present. The XAdES properties are optional, as in Office.
    targets = {
        _PACKAGE_OBJECT_ID: (f"{{{_DS_NS}}}Object", _DS_OBJECT_TYPE, True),
        _OFFICE_OBJECT_ID: (f"{{{_DS_NS}}}Object", _DS_OBJECT_TYPE, True),
        _SIGNED_PROPERTIES_ID: (
            f"{{{_XADES_NS}}}SignedProperties",
            _XADES_SIGNED_PROPERTIES_TYPE,
            False,
        ),
    }
    signed_targets: set[str] = set()
    for reference in signed_info.findall(f"{{{_DS_NS}}}Reference"):
        uri = reference.attrib.get("URI", "")
        identifier = uri[1:]
        if not uri.startswith("#") or identifier not in targets:
            return verdict("signed_info_invalid")
        tag, reference_type, _ = targets[identifier]
        target = identified.get(identifier)
        if (
            identifier in signed_targets
            or target is None
            or target.tag != tag
            or reference.attrib.get("Type", reference_type) != reference_type
        ):
            return verdict("signed_info_invalid")
        signed_targets.add(identifier)
        transforms = _reference_transforms(reference)
        if transforms is None:
            return verdict("signed_info_invalid")
        if (
            any(
                transform.attrib.get("Algorithm") != _INCLUSIVE_C14N or len(transform)
                for transform in transforms
            )
            or len(transforms) > 1
        ):
            return verdict("algorithm_unsupported")
        if (
            code := _reference_digest_code(reference, _canonical_xml(target))
        ) is not None:
            return verdict(code)
    if (
        not {identifier for identifier, (_, _, required) in targets.items() if required}
        <= signed_targets
        or identified[_PACKAGE_OBJECT_ID].getparent() is not root
    ):
        return verdict("signed_info_invalid")

    manifests = identified[_PACKAGE_OBJECT_ID].findall(f"{{{_DS_NS}}}Manifest")
    if len(manifests) != 1:
        return verdict("manifest_missing")
    covered: dict[str, frozenset[str] | None] = {}
    for reference in manifests[0].findall(f"{{{_DS_NS}}}Reference"):
        uri = reference.attrib.get("URI")
        if uri is None:
            return verdict("reference_missing")
        path, separator, content_type = uri.partition("?ContentType=")
        member = path.removeprefix("/")
        if (
            not separator
            or not path.startswith("/")
            or member not in parts
            or member.startswith(_SIGNATURE_PREFIX)
        ):
            return verdict("reference_missing")
        if member in covered:
            return verdict("reference_duplicate")
        if content_type != package.content_type(member):
            return verdict("reference_missing")
        transforms = _reference_transforms(reference)
        if transforms is None:
            return verdict("reference_missing")
        algorithms = [transform.attrib.get("Algorithm") for transform in transforms]
        source_ids: frozenset[str] | None = None
        if not algorithms:
            digested = parts[member]
        elif algorithms == [_RELATIONSHIP_TRANSFORM, _INCLUSIVE_C14N] and (
            _relationship_source(member) is not None and not len(transforms[1])
        ):
            source_ids = _relationship_source_ids(transforms[0])
            if source_ids is None:
                return verdict("algorithm_unsupported")
            try:
                digested = _relationship_transform(parts[member], source_ids, etree)
            except (etree.XMLSyntaxError, ValueError):
                return verdict("digest_mismatch")
        else:
            return verdict("algorithm_unsupported")
        covered[member] = source_ids
        if (code := _reference_digest_code(reference, digested)) is not None:
            return verdict(code)
    try:
        expected = _office_manifest(parts, package.content_type)
    except (ET.ParseError, ValueError):
        return verdict("coverage_incomplete")
    for member, signed_ids in expected.items():
        if member not in covered:
            return verdict("coverage_incomplete")
        selection = covered[member]
        # A raw digest of a relationship part covers every relationship in it.
        if (
            signed_ids is not None
            and selection is not None
            and not set(signed_ids) <= selection
        ):
            return verdict("coverage_incomplete")
    return PptxDigitalSignature(part, signer, timestamp, True, None)

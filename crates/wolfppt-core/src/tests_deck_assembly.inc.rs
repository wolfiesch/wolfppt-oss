    fn validate_package_integrity(path: impl AsRef<Path>) {
        let file = File::open(path.as_ref()).expect("open output pptx");
        let mut archive = ZipArchive::new(file).expect("open zip archive");

        let mut entry_names = HashSet::new();
        for i in 0..archive.len() {
            entry_names.insert(archive.by_index(i).unwrap().name().unwrap().into_owned());
        }

        // 1. Check [Content_Types].xml covers every part
        let content_types_str = {
            let mut file = archive.by_name("[Content_Types].xml").expect("find [Content_Types].xml");
            let mut s = String::new();
            file.read_to_string(&mut s).unwrap();
            s
        };

        let mut content_type_defaults = HashMap::new();
        let mut content_type_overrides = HashMap::new();
        {
            let mut reader = Reader::from_str(&content_types_str);
            reader.config_mut().trim_text(true);
            loop {
                match reader.read_event() {
                    Ok(Event::Empty(e)) | Ok(Event::Start(e)) => {
                        let qname = e.name();
                        let name = local_name(qname.as_ref().as_bytes());
                        if name == b"Default" {
                            let mut ext = String::new();
                            let mut ct = String::new();
                            for attr in e.attributes().flatten() {
                                if attr.key.local_name().as_ref() == "Extension" {
                                    ext = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().to_ascii_lowercase();
                                } else if attr.key.local_name().as_ref() == "ContentType" {
                                    ct = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().into_owned();
                                }
                            }
                            content_type_defaults.insert(ext, ct);
                        } else if name == b"Override" {
                            let mut part = String::new();
                            let mut ct = String::new();
                            for attr in e.attributes().flatten() {
                                if attr.key.local_name().as_ref() == "PartName" {
                                    part = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().into_owned();
                                } else if attr.key.local_name().as_ref() == "ContentType" {
                                    ct = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().into_owned();
                                }
                            }
                            content_type_overrides.insert(part, ct);
                        }
                    }
                    Ok(Event::Eof) | Err(_) => break,
                    _ => {}
                }
            }
        }

        for name in &entry_names {
            if name.ends_with('/') || name == "[Content_Types].xml" || name.contains("/_rels/") || name.starts_with("_rels/") {
                continue;
            }
            let part_name = if name.starts_with('/') { name.clone() } else { format!("/{name}") };
            let has_override = content_type_overrides.contains_key(&part_name);
            let ext = name.rsplit('.').next().unwrap_or("").to_ascii_lowercase();
            let has_default = content_type_defaults.contains_key(&ext);
            assert!(
                has_override || has_default,
                "part {name} in package has neither ContentType Override nor Default for extension {ext}"
            );
        }

        // 2. Check every relationship target resolves to an existing entry
        let mut all_rels_parts = Vec::new();
        for name in &entry_names {
            if name.ends_with(".rels") {
                all_rels_parts.push(name.clone());
            }
        }

        for rels_part in all_rels_parts {
            // Determine source part for this rels part
            // e.g. "ppt/_rels/presentation.xml.rels" -> "ppt/presentation.xml"
            // e.g. "_rels/.rels" -> ""
            let referring_part = if rels_part == "_rels/.rels" {
                "".to_string()
            } else {
                let without_rels = rels_part.strip_suffix(".rels").unwrap();
                let dir_end = without_rels.rfind("/_rels/").unwrap();
                let dir = &without_rels[..dir_end];
                let file_name = &without_rels[dir_end + 7..];
                format!("{dir}/{file_name}")
            };

            let rels_bytes = {
                let mut f = archive.by_name(&rels_part).unwrap();
                let mut b = Vec::new();
                f.read_to_end(&mut b).unwrap();
                b
            };
            let relationships = parse_relationships(&rels_bytes);
            for rel in relationships {
                if rel.target_mode.as_deref().map(|m| m.eq_ignore_ascii_case("External")).unwrap_or(false) {
                    continue;
                }
                let resolved = resolve_target(&referring_part, &rel.target);
                assert!(
                    entry_names.contains(&resolved),
                    "relationship in {rels_part} (id: {}, type: {}) has target '{}' resolved to '{}', which is missing in zip",
                    rel.id, rel.relationship_type, rel.target, resolved
                );
            }
        }

        // 3. Check presentation.xml IDs are unique
        let presentation_xml = {
            let mut f = archive.by_name("ppt/presentation.xml").unwrap();
            let mut b = Vec::new();
            f.read_to_end(&mut b).unwrap();
            b
        };

        let mut seen_pres_ids = HashSet::new();
        let mut slide_ids = Vec::new();
        let mut master_ids = Vec::new();

        {
            let mut reader = Reader::from_reader(presentation_xml.as_slice());
            reader.config_mut().trim_text(true);
            loop {
                match reader.read_event() {
                    Ok(Event::Empty(e)) | Ok(Event::Start(e)) => {
                        let qname = e.name();
                        let name = local_name(qname.as_ref().as_bytes());
                        if name == b"sldId" {
                            for attr in e.attributes().flatten() {
                                if attr.key.as_ref() == "id" {
                                    let val: u64 = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().parse().unwrap();
                                    slide_ids.push(val);
                                    assert!(seen_pres_ids.insert(val), "duplicate ID in presentation.xml: {val}");
                                }
                            }
                        } else if name == b"sldMasterId" {
                            for attr in e.attributes().flatten() {
                                if attr.key.as_ref() == "id" {
                                    let val: u64 = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().parse().unwrap();
                                    assert!(val >= 2147483648, "master id {val} is < 2147483648");
                                    master_ids.push(val);
                                    assert!(seen_pres_ids.insert(val), "duplicate ID in presentation.xml: {val}");
                                }
                            }
                        }
                    }
                    Ok(Event::Eof) | Err(_) => break,
                    _ => {}
                }
            }
        }
        assert!(!slide_ids.is_empty(), "presentation has no slide IDs");
        assert!(!master_ids.is_empty(), "presentation has no master IDs");

        // 4. Check layout IDs across all masters are unique and >= 2147483648
        let mut seen_layout_ids = HashSet::new();
        for name in &entry_names {
            if name.starts_with("ppt/slideMasters/slideMaster") && name.ends_with(".xml") {
                let master_bytes = {
                    let mut f = archive.by_name(name).unwrap();
                    let mut b = Vec::new();
                    f.read_to_end(&mut b).unwrap();
                    b
                };
                let mut reader = Reader::from_reader(master_bytes.as_slice());
                reader.config_mut().trim_text(true);
                loop {
                    match reader.read_event() {
                        Ok(Event::Empty(e)) | Ok(Event::Start(e)) => {
                            let qname = e.name();
                            if local_name(qname.as_ref().as_bytes()) == b"sldLayoutId" {
                                for attr in e.attributes().flatten() {
                                    if attr.key.as_ref() == "id" {
                                        let val: u64 = attr.normalized_value(quick_xml::XmlVersion::Implicit1_0).unwrap().parse().unwrap();
                                        assert!(val >= 2147483648, "layout id {val} in {name} is < 2147483648");
                                        assert!(
                                            seen_layout_ids.insert(val),
                                            "duplicate layout ID {val} across masters in package"
                                        );
                                    }
                                }
                            }
                        }
                        Ok(Event::Eof) | Err(_) => break,
                        _ => {}
                    }
                }
            }
        }
    }

    #[test]
    fn assembles_slides_from_two_source_decks_with_dedup_and_integrity() {
        let base_path = "../../fixtures/native-render/poi-bar-chart.pptx";
        let src1_path = "../../fixtures/pptx/media/png_picture.pptx";
        let src2_path = "../../fixtures/pptx/slides/two_slide_text.pptx";

        let dir = tempfile::tempdir().unwrap();
        let out_path = dir.path().join("assembled.pptx");

        let selections = vec![
            DeckSlideSelection {
                source_path: PathBuf::from(src1_path),
                slide_part: "ppt/slides/slide1.xml".to_string(),
            },
            DeckSlideSelection {
                source_path: PathBuf::from(src1_path),
                slide_part: "ppt/slides/slide1.xml".to_string(),
            },
            DeckSlideSelection {
                source_path: PathBuf::from(src2_path),
                slide_part: "ppt/slides/slide1.xml".to_string(),
            },
        ];

        let summary = assemble_deck(base_path, &out_path, &selections).expect("assemble_deck ok");

        // Assert slide counts
        assert_eq!(summary.slides_added, 3);
        assert_eq!(
            summary.slide_parts,
            vec![
                "ppt/slides/slide2.xml".to_string(),
                "ppt/slides/slide3.xml".to_string(),
                "ppt/slides/slide4.xml".to_string()
            ]
        );

        // Deduplication assertions:
        // Base has poi-bar-chart master.
        // Selection 0: adds png_picture master (1 master added), 11 layouts added, 1 media added
        // Selection 1: reuses png_picture master (1 master reused), 0 layouts added, 1 media reused
        // Selection 2: reuses standard master from selection 0 (1 master reused)
        assert_eq!(summary.masters_added, 1);
        assert_eq!(summary.masters_reused, 2);
        assert_eq!(summary.layouts_added, 11);
        assert_eq!(summary.media_added, 1);
        assert_eq!(summary.media_reused, 1);

        let pres = summarize_presentation(&out_path).expect("summarize assembled presentation");
        assert_eq!(pres.slides.len(), 4);

        // Same-layout slides share master and layout copy:
        // slide 2 and slide 3 were imported from the same source with the same layout
        let s2_rels = read_zip_text(&out_path, "ppt/slides/_rels/slide2.xml.rels");
        let s3_rels = read_zip_text(&out_path, "ppt/slides/_rels/slide3.xml.rels");
        let s2_parsed = parse_relationships(s2_rels.as_bytes());
        let s3_parsed = parse_relationships(s3_rels.as_bytes());

        let s2_layout_target = s2_parsed.iter().find(|r| r.relationship_type.ends_with("/slideLayout")).unwrap().target.clone();
        let s3_layout_target = s3_parsed.iter().find(|r| r.relationship_type.ends_with("/slideLayout")).unwrap().target.clone();
        assert_eq!(s2_layout_target, s3_layout_target, "same-layout slides must share the layout part");

        // Identical image shared once: only 1 media file in output
        let f = File::open(&out_path).unwrap();
        let mut z = ZipArchive::new(f).unwrap();
        let media_files: Vec<String> = (0..z.len())
            .map(|i| z.by_index(i).unwrap().name().unwrap().into_owned())
            .filter(|n| n.starts_with("ppt/media/"))
            .collect();
        assert_eq!(media_files.len(), 1, "identical image should be shared once in ppt/media");

        // Verify package integrity:
        // - every rel target resolves to existing zip entry
        // - every part has a content type
        // - presentation.xml IDs unique
        validate_package_integrity(&out_path);
    }

    #[test]
    fn assembles_empty_selections_preserves_base() {
        let base_path = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out_path = dir.path().join("assembled_empty.pptx");

        let summary = assemble_deck(base_path, &out_path, &[]).unwrap();
        assert_eq!(summary.slides_added, 0);
        assert_eq!(summary.masters_added, 0);
        assert_eq!(summary.masters_reused, 0);
        assert_eq!(summary.layouts_added, 0);
        assert_eq!(summary.media_added, 0);
        assert_eq!(summary.media_reused, 0);
        assert!(summary.slide_parts.is_empty());

        let pres = summarize_presentation(&out_path).unwrap();
        assert_eq!(pres.slides.len(), 2);
        validate_package_integrity(&out_path);
    }

    #[test]
    fn rejects_missing_source_slide_part() {
        let base_path = "../../fixtures/pptx/slides/two_slide_text.pptx";
        let src_path = "../../fixtures/pptx/media/png_picture.pptx";
        let dir = tempfile::tempdir().unwrap();
        let out_path = dir.path().join("assembled_err.pptx");

        let selections = vec![DeckSlideSelection {
            source_path: PathBuf::from(src_path),
            slide_part: "ppt/slides/slide99.xml".to_string(),
        }];

        let err = assemble_deck(base_path, &out_path, &selections).unwrap_err();
        assert!(err.to_string().contains("source slide part ppt/slides/slide99.xml was not found"));
    }

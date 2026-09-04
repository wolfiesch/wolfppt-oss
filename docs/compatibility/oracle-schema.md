# Semantic Oracle Schema

The Phase 0 semantic oracle is deliberately smaller than PresentationML. It is
designed to answer whether a library preserved the facts users care about most
without pretending to be a renderer.

```json
{
  "format": "wolfppt.semantic.v1",
  "path": "fixture.pptx",
  "part_count": 42,
  "parts": ["[Content_Types].xml", "ppt/presentation.xml"],
  "has_vba": false,
  "relationships": [
    {
      "source": "ppt/slides/slide1.xml",
      "id": "rId2",
      "type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
      "target": "../media/image1.png",
      "target_mode": null
    }
  ],
  "slides": [
    {
      "part": "ppt/slides/slide1.xml",
      "shape_count": 2,
      "texts": ["Title", "Body"],
      "shapes": [
        {
          "id": "2",
          "name": "Title 1",
          "kind": "shape",
          "text": "Title",
          "paragraphs": ["Title"],
          "tables": [],
          "transform": {"x": 0, "y": 0, "cx": 1000, "cy": 1000},
          "effective_transform": {"x": 0, "y": 0, "cx": 1000, "cy": 1000},
          "children": []
        }
      ],
      "notes": ["speaker note text"]
    }
  ]
}
```

## Intentional Limits

- No native layout or text wrapping.
- No font fallback modeling.
- No chart rendering.
- No inherited placeholder/theme resolution yet.
- Unknown parts are tracked at the package level first, then modeled as needed.

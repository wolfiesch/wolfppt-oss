use std::env;
use std::path::PathBuf;
use wolfppt_core::{
    add_blank_slide_from_existing_layout, add_blank_slide_from_layout_index, add_slide_image,
    add_slide_table, assemble_deck, inspect_package, replace_slide_image,
    replace_slide_image_at_index, replace_slide_text, replace_slide_text_at_index,
    replace_slide_text_run_at_index, replace_table_cell_text, roundtrip_package,
    set_slide_shape_paragraph_text_at_index, set_slide_shape_text_at_index, summarize_presentation,
    DeckSlideSelection,
};

fn main() {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        usage_and_exit();
    };
    match command.as_str() {
        "inspect" => {
            let Some(path) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let path = PathBuf::from(path);
            match inspect_package(&path) {
                Ok(manifest) => {
                    println!("{}", serde_json::to_string_pretty(&manifest).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "summary" => {
            let Some(path) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let path = PathBuf::from(path);
            match summarize_presentation(&path) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "roundtrip" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            match roundtrip_package(&input, &output) {
                Ok(manifest) => {
                    println!("{}", serde_json::to_string_pretty(&manifest).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "add-slide" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let layout_index = args.next().map(|value| parse_usize(&value));
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let result = match layout_index {
                Some(index) => add_blank_slide_from_layout_index(&input, &output, index),
                None => add_blank_slide_from_existing_layout(&input, &output),
            };
            match result {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-text" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(search) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            match replace_slide_text(&input, &output, &search, &replacement) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-text-in-slide" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(search) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            match replace_slide_text_at_index(&input, &output, slide_index, &search, &replacement) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-text-run" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(run_index) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let run_index = parse_usize(&run_index);
            match replace_slide_text_run_at_index(
                &input,
                &output,
                slide_index,
                run_index,
                &replacement,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "set-shape-text" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(shape_index) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let shape_index = parse_usize(&shape_index);
            match set_slide_shape_text_at_index(
                &input,
                &output,
                slide_index,
                shape_index,
                &replacement,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "set-paragraph-text" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(shape_index) = args.next() else {
                usage_and_exit();
            };
            let Some(paragraph_index) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let shape_index = parse_usize(&shape_index);
            let paragraph_index = parse_usize(&paragraph_index);
            match set_slide_shape_paragraph_text_at_index(
                &input,
                &output,
                slide_index,
                shape_index,
                paragraph_index,
                &replacement,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-image" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(relationship_id) = args.next() else {
                usage_and_exit();
            };
            let Some(image_path) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let image_path = PathBuf::from(image_path);
            match replace_slide_image(&input, &output, &relationship_id, &image_path) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-image-in-slide" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(relationship_id) = args.next() else {
                usage_and_exit();
            };
            let Some(image_path) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let image_path = PathBuf::from(image_path);
            match replace_slide_image_at_index(
                &input,
                &output,
                slide_index,
                &relationship_id,
                &image_path,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "add-image" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(image_path) = args.next() else {
                usage_and_exit();
            };
            let Some(x_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(y_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(cx_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(cy_emu) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let image_path = PathBuf::from(image_path);
            let x_emu = parse_i64(&x_emu);
            let y_emu = parse_i64(&y_emu);
            let cx_emu = parse_u64(&cx_emu);
            let cy_emu = parse_u64(&cy_emu);
            match add_slide_image(
                &input,
                &output,
                slide_index,
                &image_path,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "replace-table-cell" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(table_index) = args.next() else {
                usage_and_exit();
            };
            let Some(row_index) = args.next() else {
                usage_and_exit();
            };
            let Some(col_index) = args.next() else {
                usage_and_exit();
            };
            let Some(replacement) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let table_index = parse_usize(&table_index);
            let row_index = parse_usize(&row_index);
            let col_index = parse_usize(&col_index);
            match replace_table_cell_text(
                &input,
                &output,
                slide_index,
                table_index,
                row_index,
                col_index,
                &replacement,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "add-table" => {
            let Some(input) = args.next() else {
                usage_and_exit();
            };
            let Some(output) = args.next() else {
                usage_and_exit();
            };
            let Some(slide_index) = args.next() else {
                usage_and_exit();
            };
            let Some(rows) = args.next() else {
                usage_and_exit();
            };
            let Some(cols) = args.next() else {
                usage_and_exit();
            };
            let Some(x_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(y_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(cx_emu) = args.next() else {
                usage_and_exit();
            };
            let Some(cy_emu) = args.next() else {
                usage_and_exit();
            };
            if args.next().is_some() {
                usage_and_exit();
            }
            let input = PathBuf::from(input);
            let output = PathBuf::from(output);
            let slide_index = parse_usize(&slide_index);
            let rows = parse_usize(&rows);
            let cols = parse_usize(&cols);
            let x_emu = parse_u64(&x_emu);
            let y_emu = parse_u64(&y_emu);
            let cx_emu = parse_u64(&cx_emu);
            let cy_emu = parse_u64(&cy_emu);
            match add_slide_table(
                &input,
                &output,
                slide_index,
                rows,
                cols,
                x_emu,
                y_emu,
                cx_emu,
                cy_emu,
            ) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        "assemble-deck" => {
            let raw_args: Vec<String> = args.collect();
            let mut base_path: Option<PathBuf> = None;
            let mut output_path: Option<PathBuf> = None;
            let mut selections: Vec<DeckSlideSelection> = Vec::new();

            let mut idx = 0;
            while idx < raw_args.len() {
                let arg = &raw_args[idx];
                match arg.as_str() {
                    "--base" | "-b" => {
                        idx += 1;
                        if idx >= raw_args.len() {
                            usage_and_exit();
                        }
                        base_path = Some(PathBuf::from(&raw_args[idx]));
                    }
                    "--output" | "-o" => {
                        idx += 1;
                        if idx >= raw_args.len() {
                            usage_and_exit();
                        }
                        output_path = Some(PathBuf::from(&raw_args[idx]));
                    }
                    "--select" | "-s" => {
                        idx += 1;
                        while idx < raw_args.len() && !raw_args[idx].starts_with('-') {
                            let spec = &raw_args[idx];
                            if spec.starts_with('[') {
                                if let Ok(parsed) =
                                    serde_json::from_str::<Vec<DeckSlideSelection>>(spec)
                                {
                                    selections.extend(parsed);
                                    idx += 1;
                                    continue;
                                }
                            }
                            if let Some(colon) = spec.rfind(':') {
                                selections.push(DeckSlideSelection {
                                    source_path: PathBuf::from(&spec[..colon]),
                                    slide_part: spec[colon + 1..].to_string(),
                                });
                            } else {
                                eprintln!(
                                    "invalid selection spec: {spec}, expected SRC_PATH:SLIDE_PART"
                                );
                                std::process::exit(2);
                            }
                            idx += 1;
                        }
                        continue;
                    }
                    "--json" | "--selections-json" => {
                        idx += 1;
                        if idx >= raw_args.len() {
                            usage_and_exit();
                        }
                        match serde_json::from_str::<Vec<DeckSlideSelection>>(&raw_args[idx]) {
                            Ok(parsed) => selections.extend(parsed),
                            Err(err) => {
                                eprintln!("invalid selections JSON: {err}");
                                std::process::exit(2);
                            }
                        }
                    }
                    other => {
                        if base_path.is_none() {
                            base_path = Some(PathBuf::from(other));
                        } else if output_path.is_none() {
                            output_path = Some(PathBuf::from(other));
                        } else if let Some(colon) = other.rfind(':') {
                            selections.push(DeckSlideSelection {
                                source_path: PathBuf::from(&other[..colon]),
                                slide_part: other[colon + 1..].to_string(),
                            });
                        } else {
                            usage_and_exit();
                        }
                    }
                }
                idx += 1;
            }

            let (Some(base), Some(output)) = (base_path, output_path) else {
                usage_and_exit();
            };

            match assemble_deck(&base, &output, &selections) {
                Ok(summary) => {
                    println!("{}", serde_json::to_string_pretty(&summary).unwrap());
                }
                Err(err) => {
                    eprintln!("{err}");
                    std::process::exit(1);
                }
            }
        }
        _ => usage_and_exit(),
    }
}

fn parse_usize(value: &str) -> usize {
    value.parse().unwrap_or_else(|_| {
        eprintln!("expected non-negative integer, got {value}");
        std::process::exit(2);
    })
}

fn parse_u64(value: &str) -> u64 {
    value.parse().unwrap_or_else(|_| {
        eprintln!("expected non-negative integer, got {value}");
        std::process::exit(2);
    })
}

fn parse_i64(value: &str) -> i64 {
    value.parse().unwrap_or_else(|_| {
        eprintln!("expected signed 64-bit integer, got {value}");
        std::process::exit(2);
    })
}

fn usage_and_exit() -> ! {
    eprintln!(
        "usage: wolfppt-cli <inspect|summary> <presentation.pptx|presentation.pptm>\n       wolfppt-cli roundtrip <input.pptx|input.pptm> <output.pptx|output.pptm>"
    );
    eprintln!(
        "       wolfppt-cli add-slide <input.pptx|input.pptm> <output.pptx|output.pptm> [layout-index]"
    );
    eprintln!(
        "       wolfppt-cli replace-text <input.pptx|input.pptm> <output.pptx|output.pptm> <search> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli replace-text-in-slide <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <search> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli replace-text-run <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <run-index> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli set-shape-text <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <shape-index> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli set-paragraph-text <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <shape-index> <paragraph-index> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli replace-image <input.pptx|input.pptm> <output.pptx|output.pptm> <relationship-id> <image>"
    );
    eprintln!(
        "       wolfppt-cli replace-image-in-slide <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <relationship-id> <image>"
    );
    eprintln!(
        "       wolfppt-cli add-image <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <image> <x-emu> <y-emu> <cx-emu> <cy-emu>"
    );
    eprintln!(
        "       wolfppt-cli replace-table-cell <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <table-index> <row-index> <col-index> <replacement>"
    );
    eprintln!(
        "       wolfppt-cli add-table <input.pptx|input.pptm> <output.pptx|output.pptm> <slide-index> <rows> <cols> <x-emu> <y-emu> <cx-emu> <cy-emu>"
    );
    eprintln!(
        "       wolfppt-cli assemble-deck --base BASE --output OUT --select SRC:ppt/slides/slide2.xml ..."
    );
    std::process::exit(2)
}

import sys
import os
import importlib
import za_parser.model


def main():
    if len(sys.argv) < 2:
        print("Usage: python ZAassetExtraction.py <input.dat> [output_folder]")
        sys.exit(1)

    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print(f"Error: file not found: {input_file}")
        sys.exit(1)

    output_folder = sys.argv[2] if len(sys.argv) > 2 else "export"

    print(f"Loading: {input_file}")
    game = za_parser.model.Game(input_file)

    print(f"Exporting assets to: {output_folder}")
    game.export(
        output_folder,
        templateFolder="curiosity_templates",
        libraryScriptFolder="library_scripts"
    )

    print("Done.")


if __name__ == "__main__":
    main()

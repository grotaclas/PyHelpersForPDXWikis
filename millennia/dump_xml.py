from argparse import ArgumentParser
from pathlib import Path

from millennia.unity_reader import UnityReaderMillennia

if __name__ == '__main__':
    parser = ArgumentParser(description='dump text assets by their addressables. This should include all the XML')
    parser.add_argument('output_folder', help='The output will be written into subfolders of this folder based on the addressables of the text assets', type=Path)
    args = parser.parse_args()
    unity_reader = UnityReaderMillennia()
    unity_reader.dump_text_resources(args.output_folder)

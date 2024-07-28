import os
import fnmatch
import pathspec
import argparse
from pathlib import Path
import configparser
from collections import defaultdict


def load_gitignore_patterns(gitignore_path):
    with open(gitignore_path, 'r', encoding='utf-8') as file:
        return file.read().splitlines()

def skip_swagger_annotations(lines):
    inside_swagger_block = False
    filtered_lines = []
    for line in lines:
        if '*/' in line and inside_swagger_block:
            inside_swagger_block = False
            continue
        if inside_swagger_block:
            continue
        if '/**' in line and '@swagger' in line:
            inside_swagger_block = True
            continue
        filtered_lines.append(line)
    return filtered_lines

def generate_directory_structure(file_paths, exclude_folders, exclude_files, exclude_files_ignored_by_git, output_as_directory_with_content, add_full_path):
    directory_structure = []
    gitignore_patterns = []
    if exclude_files_ignored_by_git:
        for path in file_paths:
            gitignore_path = os.path.join(path, '.gitignore')
            if os.path.isfile(gitignore_path):
                gitignore_patterns.extend(load_gitignore_patterns(gitignore_path))
    
    spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_patterns)

    def is_excluded(path):
        abs_path = os.path.abspath(path)
        if any(os.path.commonpath([exclude_folder, abs_path]) == exclude_folder for exclude_folder in exclude_folders):
            return True
        if any(fnmatch.fnmatch(os.path.basename(abs_path), pattern) for pattern in exclude_files):
            return True
        if exclude_files_ignored_by_git and spec.match_file(abs_path):
            return True
        return False

    for path in file_paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                if is_excluded(root):
                    continue
                level = root.replace(str(path), '').count(os.sep)
                indent = ' ' * 4 * level
                directory_structure.append(f"{os.path.abspath(root)}/" if add_full_path else f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    file_path = os.path.join(root, f)
                    if not is_excluded(file_path):
                        directory_structure.append(f"{os.path.abspath(file_path)}" if add_full_path else f"{subindent}{f}")
                        if output_as_directory_with_content:
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                                    lines = infile.readlines()
                                    file_content = ''.join([f"{subindent}    {line}" for line in lines])
                                    directory_structure.append(file_content)
                            except Exception as e:
                                directory_structure.append(f"{subindent}    Error reading {file_path}: {e}")
    return directory_structure

def concatenate_files(file_paths, output_file, exclude_folders, exclude_files_ignored_by_git, exclude_files, include_files, output_as_directory_with_content, add_full_path, exclude_swagger_annotations):
    all_files = []
    exclude_folders = [str(Path(folder).resolve()) for folder in exclude_folders if folder.strip()] if exclude_folders else []
    exclude_files = [pattern for pattern in exclude_files if pattern.strip()] if exclude_files else []
    include_files = [pattern for pattern in include_files if pattern.strip()] if include_files else ['*']

    # Add default media file exclusions
    default_media_exclusions = [
        '*.mp3', '*.wav', '*.wma', '*.aac',  # Audio files
        '*.mp4', '*.avi', '*.mov', '*.mkv', '*.flv', '*.wmv',  # Video files
        '*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp', '*.tiff', '*.svg', '*.webp', '*.jfif'  # Image files
    ]
    exclude_files.extend(default_media_exclusions)

    # Add output_file to exclude_files to avoid including it in the concatenation
    exclude_files.append(output_file)
    
    # Generate directory structure
    directory_structure = generate_directory_structure(file_paths, exclude_folders, exclude_files, exclude_files_ignored_by_git, output_as_directory_with_content, add_full_path)

    gitignore_patterns = []
    if exclude_files_ignored_by_git:
        for path in file_paths:
            gitignore_path = os.path.join(path, '.gitignore')
            if os.path.isfile(gitignore_path):
                gitignore_patterns.extend(load_gitignore_patterns(gitignore_path))
    
    spec = pathspec.PathSpec.from_lines('gitwildmatch', gitignore_patterns)

    def is_excluded(path):
        abs_path = os.path.abspath(path)
        if any(os.path.commonpath([exclude_folder, abs_path]) == exclude_folder for exclude_folder in exclude_folders):
            return True
        if any(fnmatch.fnmatch(os.path.basename(abs_path), pattern) for pattern in exclude_files):
            return True
        if exclude_files_ignored_by_git and spec.match_file(abs_path):
            return True
        return False

    def is_included(path):
        abs_path = os.path.abspath(path)
        return any(fnmatch.fnmatch(os.path.basename(abs_path), pattern) for pattern in include_files)
    
    print("Starting file concatenation process...")

    folder_stats = defaultdict(lambda: {'files': 0, 'lines': 0})
    total_files_found = 0
    for path in file_paths:
        path = str(path)
        if os.path.isfile(path):
            if not is_excluded(path) and is_included(path):
                all_files.append(path)
                total_files_found += 1
                folder_stats[os.path.dirname(path)]['files'] += 1
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                if is_excluded(root):
                    continue
                for file in files:
                    file_path = os.path.join(root, file)
                    if not is_excluded(file_path) and is_included(file_path):
                        all_files.append(file_path)
                        total_files_found += 1
                        folder_stats[root]['files'] += 1
        else:
            print(f"Path {path} is neither a file nor a directory. Skipping...")
    
    print(f"Total files found: {total_files_found}")
    
    total_files_processed = 0
    total_lines = 0
    with open(output_file, 'w', encoding='utf-8') as outfile:
        # Write the directory structure at the beginning of the file
        outfile.write("Directory Structure:\n")
        outfile.write("\n".join(directory_structure))
        outfile.write("\n\n")
        
        if not output_as_directory_with_content:
            for file_path in all_files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        lines = infile.readlines()
                        if exclude_swagger_annotations:
                            lines = skip_swagger_annotations(lines)
                        line_count = len(lines)
                        total_lines += line_count
                        folder_stats[os.path.dirname(file_path)]['lines'] += line_count
                        outfile.write(f"// {file_path}\n")
                        outfile.writelines(lines)
                        outfile.write("\n")
                    total_files_processed += 1
                    if total_files_processed % 10 == 0 or total_files_processed == total_files_found:
                        print(f"Processed {total_files_processed} of {total_files_found} files...")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    output_file_size = os.path.getsize(output_file)
    print("****************************************")
    print("* File concatenation process completed *")
    print("****************************************")
    print(f"Total files processed: {total_files_processed}")
    print(f"Total lines written: {total_lines}")
    print(f"Output file size: {output_file_size} bytes")
    
    print("\nStatistics per folder:")
    for folder, stats in folder_stats.items():
        print(f"Folder: {folder}")
        print(f"  Files concatenated: {stats['files']}")
        print(f"  Lines written: {stats['lines']}")

def load_config(config_path):
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(config_path)
    parameters = {
        "base_folder": config.get('Settings', 'base_folder', fallback='.'),
        "exclude_folders": [line.strip() for line in config.get('Settings', 'exclude_folders', fallback='').splitlines() if line.strip()],
        "exclude_files": [line.strip() for line in config.get('Settings', 'exclude_files', fallback='').splitlines() if line.strip()],
        "include_files": [line.strip() for line in config.get('Settings', 'include_files', fallback='*').splitlines() if line.strip()],
        "exclude_files_ignored_by_git": config.getboolean('Settings', 'exclude_files_ignored_by_git', fallback=True),
        "output_as_directory_with_content": config.getboolean('Settings', 'output_as_directory_with_content', fallback=True),
        "add_full_path": config.getboolean('Settings', 'add_full_path', fallback=False),
        "exclude_swagger_annotations": config.getboolean('Settings', 'exclude_swagger_annotations', fallback=False)
    }
    return parameters

def main():
    parser = argparse.ArgumentParser(description="Concatenate files with options for exclusions and inclusions.")
    parser.add_argument('file_paths', nargs='*', default=['.'], help='List of files or directories to process. Defaults to the current directory.')
    parser.add_argument('-o', '--output', default='ConcatenateResult.txt', help='Output file to write concatenated content. Defaults to ConcatenateResult.txt.')
    parser.add_argument('--exclude-folders', nargs='*', default=[], help='Folders to exclude from processing.')
    parser.add_argument('--exclude-files', nargs='*', default=[], help='Files to exclude from processing by pattern.')
    parser.add_argument('--include-files', nargs='*', default=['*'], help='Files to include in processing by pattern.')
    parser.add_argument('--exclude-files-ignored-by-git', action='store_true', default=True, help='Exclude files ignored by git. Enabled by default.')
    parser.add_argument('--output-as-directory-with-content', action='store_true', default=True, help='Output directory structure with content. Enabled by default.')
    parser.add_argument('--add-full-path', action='store_true', default=False, help='Add full path instead of indentation. Disabled by default.')
    parser.add_argument('--exclude-swagger-annotations', action='store_true', default=False, help='Exclude Swagger annotations from the output. Disabled by default.')

    args = parser.parse_args()

    # Check if .cacaito file exists in the current directory
    cacaito_path = Path('.cacaito')
    if cacaito_path.is_file():
        print("Loading configuration from .cacaito file...")
        config_parameters = load_config(cacaito_path)
        base_folder = config_parameters['base_folder']
        args.exclude_folders = config_parameters['exclude_folders']
        args.exclude_files = config_parameters['exclude_files']
        args.include_files = config_parameters['include_files']
        args.exclude_files_ignored_by_git = config_parameters['exclude_files_ignored_by_git']
        args.output_as_directory_with_content = config_parameters['output_as_directory_with_content']
        args.add_full_path = config_parameters['add_full_path']
        args.exclude_swagger_annotations = config_parameters['exclude_swagger_annotations']

        # If base_folder is specified in the config, use it as the root for file_paths
        if base_folder:
            base_folder_path = Path(base_folder).resolve()
            args.file_paths = [base_folder_path]

    # Clean up empty and whitespace-only patterns
    args.exclude_folders = [folder for folder in args.exclude_folders if folder.strip()]
    args.exclude_files = [pattern for pattern in args.exclude_files if pattern.strip()]
    args.include_files = [pattern for pattern in args.include_files if pattern.strip()]

    print("Final configurations:")
    print(f"Base Folder: {args.file_paths[0]}")
    print(f"Exclude Folders: {args.exclude_folders}")
    print(f"Exclude Files: {args.exclude_files}")
    print(f"Include Files: {args.include_files}")
    print(f"Exclude Files Ignored by Git: {args.exclude_files_ignored_by_git}")
    print(f"Output As Directory With Content: {args.output_as_directory_with_content}")
    print(f"Add Full Path: {args.add_full_path}")
    print(f"Exclude Swagger Annotations: {args.exclude_swagger_annotations}")

    concatenate_files(
        file_paths=args.file_paths,
        output_file=args.output,
        exclude_folders=args.exclude_folders,
        exclude_files_ignored_by_git=args.exclude_files_ignored_by_git,
        exclude_files=args.exclude_files,
        include_files=args.include_files,
        output_as_directory_with_content=args.output_as_directory_with_content,
        add_full_path=args.add_full_path,
        exclude_swagger_annotations=args.exclude_swagger_annotations
    )

if __name__ == "__main__":
    main()

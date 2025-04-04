import subprocess
import yaml
from datetime import datetime


def get_git_history(reversed=False):
    if reversed:
        cmd = ['git', 'log', '--pretty=format:%h|%s|%ad', '--date=iso', '--reverse']
    else:
        cmd = ['git', 'log', '--pretty=format:%h|%s|%ad', '--date=iso']
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [line.split('|') for line in result.stdout.splitlines()]


def get_version_changes():
    history = get_git_history(reversed=True)
    version_changes = []
    last_version = None
    
    for commit in history:
        try:
            # Check if build_config.yaml exists in this commit
            exists = subprocess.run(['git', 'cat-file', '-e', f'{commit[0]}:build_config.yaml'],
                                  capture_output=True)
            if exists.returncode != 0:
                continue
                
            # Get the actual build_config.yaml content
            content = subprocess.run(['git', 'show', f'{commit[0]}:build_config.yaml'],
                                   capture_output=True, text=True)
            config = yaml.safe_load(content.stdout)
            current_version = config.get('project', {}).get('version')
            
            # Only add if version changed and is valid
            if current_version and current_version != last_version:
                version_changes.append((commit[0], current_version, commit[2], commit[1]))
                last_version = current_version
        except Exception:
            continue
    return version_changes


def generate_changelog():
    version_changes = get_version_changes()
    print(f"Found {len(version_changes)} version changes")
    for version_change in version_changes:
        print(f"{version_change[1]} ({version_change[2]}) Hash: {version_change[0]} - {version_change[-1]}")
    commits = get_git_history(reversed=False)
    
    changelog = '# Changelog for TomeFlow\n\n'
    excluded_parts = ['Merge branch', 'webpage', 'twitter', 'Facebook', 'Update Version to', 'C++', 'Webpage']
    
    # Iterate through version changes in reverse order (newest first)
    for i, (commit_hash, version, date, commit_message) in enumerate(version_changes):
        start_date = date
        end_date = version_changes[i+1][2] if i+1 < len(version_changes) else datetime.now().strftime('%Y-%m-%d %H:%M:%S%z')
        
        simplified_start_date_for_changelog = start_date.split(' ')[0]
        simplified_end_date_for_changelog = end_date.split(' ')[0]

        changelog += f'## Version {version} ({simplified_start_date_for_changelog})\n\n'
        last_version = version_changes[i+1][1] if i+1 < len(version_changes) else None
        # changelog += f'*Version updated in commit {commit_hash[:7]} (from {last_version} to {version}): {commit_message}*\n\n'
        # Add commits for this version period
        for commit in commits:
            commit_date = commit[2]
            if start_date <= commit_date < end_date:
                for part in excluded_parts:
                    if part in commit[1]:
                        break
                else:
                    if i == len(version_changes) - 1:
                        if commit_date > start_date:
                            print(f"Skipping commit {commit[0]}: {commit[1]}")
                            continue
                    changelog += f'- {commit[1]}\n'
        changelog += '\n'
    
    with open('CHANGELOG.md', 'w') as f:
        f.write(changelog)


if __name__ == '__main__':
    generate_changelog()

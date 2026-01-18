#!/usr/bin/env python3
"""Extract conversation from Claude Code's jsonl file and save to database."""

import sqlite3
import json
import sys
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Base path for the skill - database stored in skill directory
BASE_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = BASE_PATH / "conversations.db"

# Default Claude Code projects directory
PROJECTS_DIR = Path("C:/Users/86155/.claude/projects")

# China timezone (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

def get_current_session_file():
    """Find the most recent jsonl session file from any project directory."""

    # Collect all jsonl files from all project directories
    all_jsonl_files = []

    # Search in all project directories
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            jsonl_files = list(project_dir.glob("*.jsonl"))
            all_jsonl_files.extend(jsonl_files)

    if all_jsonl_files:
        # Return the most recently modified file
        return max(all_jsonl_files, key=lambda f: f.stat().st_mtime)

    return None

def extract_session_id(jsonl_file):
    """Extract session ID from jsonl file path."""

    # Session ID is the filename without extension
    return jsonl_file.stem

def get_existing_session_info(session_id):
    """Get existing conversation info for this session.

    Returns the base title (without version suffix) and max version.
    """

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, MAX(version) as max_version
        FROM conversations
        WHERE session_id = ?
        GROUP BY title
        ORDER BY max_version DESC
        LIMIT 1
    """, (session_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        # Remove version suffix (e.g., " v2") from title
        title = result[0]
        base_title = re.sub(r' v\d+$', '', title)
        return base_title, result[1]  # (base_title, max_version)
    return None, None

def extract_conversation(jsonl_file):
    """Extract user and assistant messages from jsonl file.

    Returns a formatted conversation string.
    """

    messages = []

    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            try:
                data = json.loads(line)

                # Skip non-message entries
                if data.get('type') not in ['user', 'assistant']:
                    continue

                # Extract message content
                if 'message' in data:
                    msg = data['message']
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')

                    # Handle content as list (structured content)
                    if isinstance(content, list):
                        content_text = []
                        for item in content:
                            if isinstance(item, dict):
                                if item.get('type') == 'text':
                                    content_text.append(item.get('text', ''))
                                elif item.get('type') == 'tool_use':
                                    # Skip tool_use entries for cleaner output
                                    continue
                                elif item.get('type') == 'tool_result':
                                    # Skip tool_result entries
                                    continue
                            elif isinstance(item, str):
                                content_text.append(item)

                        content = '\n'.join(content_text).strip()

                    if content:
                        timestamp = data.get('timestamp', '')
                        if timestamp:
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                # Convert to China timezone
                                dt_china = dt.astimezone(CHINA_TZ)
                                time_str = dt_china.strftime('%H:%M')
                            except:
                                time_str = ''
                        else:
                            time_str = ''

                        messages.append({
                            'role': role,
                            'content': content,
                            'time': time_str
                        })

            except json.JSONDecodeError:
                continue

    # Format conversation
    formatted = []
    for msg in messages:
        role_name = 'User' if msg['role'] == 'user' else 'Assistant'
        time_str = f" [{msg['time']}]" if msg['time'] else ''
        formatted.append(f"{role_name}{time_str}: {msg['content']}")

    return '\n\n'.join(formatted)

def generate_summary(content, messages_count):
    """Generate a meaningful summary from conversation content.

    Extracts key topics and actions to create a concise summary.
    """

    # Extract all user messages
    user_messages = []
    for line in content.split('\n'):
        if line.startswith('User:') or line.startswith('User ['):
            # Extract the user's message content
            msg_content = line.split(':', 1)[1].strip()
            if msg_content:
                user_messages.append(msg_content)

    if not user_messages:
        # Fallback if no user messages found
        return f"包含 {messages_count} 条消息的对话记录。"

    # Extract key information from user messages
    topics = []
    actions = []

    # Common action patterns
    action_patterns = [
        r'(帮我|请|帮我创建|帮我写|帮我实现|帮我生成|帮我修复|帮我优化)',
        r'(创建|实现|写|生成|修复|优化|分析|检查|测试)',
        r'(save|保存|export|导出|load|加载|search|搜索)',
    ]

    # Topic patterns
    topic_patterns = [
        r'(技能|skill|功能|feature|系统|system|项目|project)',
        r'(代码|code|文件|file|数据库|database|API|web|界面)',
        r'(问题|bug|错误|error|失败|failed)',
        r'(对话|conversation|聊天|chat|历史|history)',
    ]

    for msg in user_messages[:5]:  # Only check first 5 user messages
        # Check for actions
        for pattern in action_patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                # Extract the main verb/action
                match = re.search(pattern, msg, re.IGNORECASE)
                if match:
                    action = match.group(1)
                    if action not in actions:
                        actions.append(action)

        # Check for topics
        for pattern in topic_patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                match = re.search(pattern, msg, re.IGNORECASE)
                if match:
                    topic = match.group(1)
                    if topic not in topics:
                        topics.append(topic)

    # Build summary
    summary_parts = []

    # Add message count
    summary_parts.append(f"对话包含 {messages_count} 条消息")

    # Add topics if found
    if topics:
        topics_str = '、'.join(topics[:3])  # Limit to 3 topics
        summary_parts.append(f"，主要涉及{topics_str}")

    # Add actions if found
    if actions:
        actions_str = '、'.join(actions[:3])  # Limit to 3 actions
        summary_parts.append(f"，进行了{actions_str}等操作")

    # Combine summary parts
    summary = ''.join(summary_parts) + '。'

    # Ensure summary is not too long
    if len(summary) > 200:
        summary = summary[:197] + '...'

    return summary

def save_conversation(content: str, session_id: str, title: str = None, summary: str = None, tags: str = None, project_name: str = None):
    """Save a conversation to the database with version control."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count messages for summary generation
    user_count = content.count('\nUser') + content.count('User [')
    assistant_count = content.count('\nAssistant') + content.count('Assistant [')
    total_messages = user_count + assistant_count

    # Check for existing conversation with same session_id
    existing_title, max_version = get_existing_session_info(session_id)

    # Determine title and version
    if title:
        # User provided title, check if we should add version
        if existing_title and title == existing_title:
            # Same title as existing, add version
            version = (max_version or 0) + 1
            display_title = f"{title} v{version}"
        else:
            # New title or different from existing
            version = 1
            display_title = title
    else:
        # Auto-generate title
        if existing_title:
            # Use existing title with new version
            version = (max_version or 0) + 1
            display_title = f"{existing_title} v{version}"
        else:
            # First time, generate new title
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines:
                first_user_msg = next((l for l in lines if l.startswith('User:')), lines[0])
                base_title = first_user_msg[:60] + "..." if len(first_user_msg) > 60 else first_user_msg
            else:
                now_china = datetime.now(CHINA_TZ)
                base_title = f"Conversation {now_china.strftime('%Y-%m-%d %H:%M')}"
            version = 1
            display_title = base_title

    # Generate summary if not provided
    if not summary:
        summary = generate_summary(content, total_messages)

    # Timestamp - use China time (UTC+8)
    created_at = datetime.now(CHINA_TZ).isoformat()

    # Insert conversation with session tracking
    cursor.execute("""
        INSERT INTO conversations (title, summary, content, tags, project_name, created_at, session_id, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (display_title, summary, content, tags, project_name, created_at, session_id, version))

    conversation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return conversation_id, display_title, version

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Save conversation from jsonl file')
    parser.add_argument('--file', help='Path to jsonl file (auto-detect if not provided)')
    parser.add_argument('--title', help='Conversation title')
    parser.add_argument('--tags', help='Comma-separated tags')
    parser.add_argument('--project', help='Project name')

    args = parser.parse_args()

    # Get jsonl file path
    if args.file:
        jsonl_file = Path(args.file)
    else:
        jsonl_file = get_current_session_file()
        if not jsonl_file:
            print("Error: Could not find jsonl session file")
            print("Please specify the file path with --file option")
            sys.exit(1)

    print(f"Reading conversation from: {jsonl_file}")

    # Extract session ID
    session_id = extract_session_id(jsonl_file)
    print(f"Session ID: {session_id}")

    # Extract conversation
    content = extract_conversation(jsonl_file)

    if not content:
        print("Error: No conversation content found")
        sys.exit(1)

    print(f"Extracted {len(content)} characters")

    # Save to database with version control
    conversation_id, title, version = save_conversation(content, session_id, args.title, None, args.tags, args.project)

    print(f"Conversation saved with ID: {conversation_id}")
    print(f"Title: {title}")
    print(f"Version: {version}")

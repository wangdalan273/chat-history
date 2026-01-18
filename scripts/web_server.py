#!/usr/bin/env python3
"""Flask web server for chat history management."""

import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import Flask, jsonify, request, render_template_string, send_file

# China timezone (UTC+8)
CHINA_TZ = timezone(timedelta(hours=8))

# Base path for the skill
BASE_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = BASE_PATH / "conversations.db"
EXPORTS_DIR = BASE_PATH / "exports"
PROJECTS_DIR = Path("C:/Users/86155/.claude/projects")

# Ensure exports directory exists
EXPORTS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

def get_db_connection():
    """Get database connection."""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create conversations table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            title TEXT,
            summary TEXT,
            content TEXT,
            tags TEXT,
            project_name TEXT,
            created_at TEXT,
            message_count INTEGER,
            is_starred INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add is_starred column if it doesn't exist (for backwards compatibility)
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_starred' not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN is_starred INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

def format_datetime(iso_string):
    """Format ISO datetime string to China timezone (UTC+8)."""

    try:
        dt = datetime.fromisoformat(iso_string)
        # Convert to China timezone if not already
        if dt.tzinfo is None:
            # No timezone info, assume it's already in China time
            return dt.strftime("%Y-%m-%d %H:%M")
        else:
            # Has timezone info, convert to China timezone
            dt_china = dt.astimezone(CHINA_TZ)
            return dt_china.strftime("%Y-%m-%d %H:%M")
    except:
        # Fallback: return first 16 chars
        return iso_string[:16]

def scan_jsonl_files():
    """Scan all project directories for jsonl session files."""

    jsonl_files = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            for jsonl_file in project_dir.glob("*.jsonl"):
                jsonl_files.append(jsonl_file)
    return jsonl_files

def generate_smart_title(user_messages):
    """Generate a smart title by analyzing the entire conversation context."""

    import re
    from collections import Counter

    if not user_messages:
        return "对话记录"

    # Analyze multiple messages to understand the conversation
    all_msgs = user_messages[:8]  # Analyze first 8 messages
    all_text = ' '.join(all_msgs).lower()

    # Step 1: Detect the main task/topic from the conversation
    task_indicators = {
        '添加功能': ['添加', '新增', '增加', '加上', '增加一个'],
        '修复问题': ['修复', '解决', '修复bug', '解决bug', '报错', '错误'],
        '优化代码': ['优化', '改进', '重构', '提高性能'],
        '实现功能': ['实现', '开发', '创建', '编写', '做一个'],
        '学习使用': ['怎么用', '如何使用', '怎么', '怎样', '如何'],
        '配置部署': ['部署', '配置', '安装', '设置', '环境'],
        '数据处理': ['分析', '处理数据', '数据', '统计'],
        '界面设计': ['界面', '页面', 'ui', '样式', '布局'],
        'Git操作': ['git', '提交', '推送', '分支', '版本', '仓库'],
        'API开发': ['api', '接口', '请求', 'endpoint'],
    }

    # Find the dominant task
    task_scores = {}
    for task, keywords in task_indicators.items():
        score = sum(all_text.count(kw) for kw in keywords)
        if score > 0:
            task_scores[task] = score

    # Step 2: Extract the core subject/objects from conversation
    # Look for nouns and technical terms that appear frequently
    subjects = []

    # Common tech terms to look for
    tech_patterns = [
        r'(?:功能|系统|项目|模块|组件)(?:叫做|名称|是)?[：:]?\s*([a-zA-Z0-9_\u4e00-\u9fa5]{2,15})',
        r'(?:开发|实现|添加|创建)(?:了|一个|了?个|了?)?\s*([a-zA-Z0-9_\u4e00-\u9fa5]{2,15})',
        r'([a-zA-Z0-9_]{3,20})(?:功能|模块|系统|类)',
    ]

    for pattern in tech_patterns:
        matches = re.findall(pattern, all_text)
        subjects.extend(matches)

    # Extract nouns/phrases from first few messages
    for msg in all_msgs[:5]:
        # Look for patterns like "关于XXX" "针对XXX" "XXX相关"
        about_matches = re.findall(r'(?:关于|针对|处理)([^\n，。]{2,12})', msg)
        subjects.extend(about_matches)

        # Look for direct object patterns
        object_matches = re.findall(r'(?:添加|实现|创建|开发|写|生成|做一个|做个)\s*([^\n，。]{2,15})', msg)
        subjects.extend(object_matches)

    # Count subject frequency
    subject_counter = Counter(subjects)
    if subject_counter:
        main_subject = subject_counter.most_common(1)[0][0].strip()
        # Clean up the subject
        main_subject = main_subject.replace('功能', '').replace('模块', '').replace('系统', '').strip()
        if len(main_subject) >= 2 and len(main_subject) <= 10:
            # Combine with task
            if task_scores:
                main_task = max(task_scores, key=task_scores.get)
                return f"{main_subject} - {main_task}"
            return main_subject

    # Step 3: Analyze the first message more carefully
    first_msg = user_messages[0].strip()

    # Pattern: User wants to do something
    want_patterns = [
        (r'(?:我想|我要|帮我)(?:开发|实现|添加|创建|做一个)?\s*([^\n，。]{2,15})(?:功能|一下)?', 'create'),
        (r'(?:学习|了解|知道)(?:一下)?([^\n，。]{2,15})', 'learn'),
        (r'(?:优化|改进)([^\n，。]{2,15})', 'optimize'),
        (r'(?:修复|解决)(?:[^\n]{0,5})?([^\n，。]{2,15})(?:问题|bug|错误)?', 'fix'),
    ]

    for pattern, action_type in want_patterns:
        match = re.search(pattern, first_msg)
        if match:
            content = match.group(1).strip()
            # Clean up
            content = re.sub(r'^(一个|这个|那个|那个|个|的|了)', '', content).strip()

            if len(content) >= 2 and len(content) <= 12:
                action_map = {
                    'create': '开发',
                    'learn': '学习',
                    'optimize': '优化',
                    'fix': '修复',
                }
                prefix = action_map.get(action_type, '')
                if prefix:
                    return f"{prefix}{content}"
                return content

    # Step 4: Extract key phrase focusing on technical content
    # Remove common conversational prefixes
    clean_first = first_msg
    for prefix in ['我现在', '我需要', '帮我', '请', '可以', '我想', '我要', '我有个']:
        if clean_first.startswith(prefix):
            clean_first = clean_first[len(prefix):].strip()
            break

    # Look for the meaningful part
    meaningful_patterns = [
        r'([^\n，。]{4,20})(?:功能|模块|系统|问题|需求)',
        r'(?:进行|实现|完成)([^\n，。]{4,16})',
        r'([^\n，。]{4,18})(?:，|。|$)',
    ]

    for pattern in meaningful_patterns:
        match = re.search(pattern, clean_first)
        if match:
            phrase = match.group(1).strip()
            if len(phrase) >= 4 and len(phrase) <= 14:
                return phrase

    # Step 5: Use dominant task as fallback
    if task_scores:
        return max(task_scores, key=task_scores.get)

    # Step 6: Final fallback - first meaningful segment
    if len(clean_first) > 15:
        for sep in ['，', '。', '的', '是', '和']:
            if sep in clean_first[:15]:
                clean_first = clean_first.split(sep)[0].strip()
                break
        else:
            clean_first = clean_first[:15].strip()

    return clean_first if clean_first else "对话记录"

def parse_jsonl_file(jsonl_file):
    """Parse a jsonl file and extract conversation info."""

    messages = []
    user_messages = []  # Collect all user messages for smart title generation
    last_timestamp = None
    message_count = 0

    try:
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
                            has_text_content = False
                            has_only_tools = True

                            for item in content:
                                if isinstance(item, dict):
                                    item_type = item.get('type', '')
                                    # Only extract text content
                                    if item_type == 'text':
                                        text_content = item.get('text', '')
                                        if text_content:
                                            content_text.append(text_content)
                                            has_text_content = True
                                            has_only_tools = False
                                    # Skip: tool_use, tool_result, thinking, image
                                    # elif item_type in ['tool_use', 'tool_result', 'thinking', 'image']:
                                    #     continue
                                elif isinstance(item, str):
                                    content_text.append(item)

                            # Skip messages that only contain tool results or thinking
                            if not has_text_content:
                                continue

                            content = '\n'.join(content_text).strip()

                        # Skip empty content or tool-only messages
                        if not content or role == 'unknown':
                            continue

                        if content:
                            # Get timestamp
                            timestamp = data.get('timestamp', '')
                            if timestamp:
                                try:
                                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    dt_china = dt.astimezone(CHINA_TZ)
                                    time_str = dt_china.strftime('%H:%M')
                                    if not last_timestamp or dt > last_timestamp:
                                        last_timestamp = dt
                                except:
                                    time_str = ''
                            else:
                                time_str = ''

                            # Collect user messages for smart title
                            if role == 'user':
                                user_messages.append(content)

                            message_count += 1
                            messages.append({
                                'role': role,
                                'content': content,
                                'time': time_str
                            })

                except json.JSONDecodeError:
                    continue

        # Format conversation content
        formatted_content = []
        for msg in messages:
            role_name = 'User' if msg['role'] == 'user' else 'Assistant'
            time_str = f" [{msg['time']}]" if msg['time'] else ''
            formatted_content.append(f"{role_name}{time_str}: {msg['content']}")
        content = '\n\n'.join(formatted_content)

        # Extract project name from directory
        project_name = jsonl_file.parent.name

        # Create summary
        summary = f"对话包含 {message_count} 条消息"

        # Generate smart title from user messages
        smart_title = generate_smart_title(user_messages) if user_messages else "对话记录"

        return {
            'session_id': jsonl_file.stem,
            'title': smart_title,
            'summary': summary,
            'content': content,
            'project_name': project_name,
            'created_at': last_timestamp.isoformat() if last_timestamp else datetime.now(CHINA_TZ).isoformat(),
            'message_count': message_count,
            'file_path': str(jsonl_file)
        }

    except Exception as e:
        return None

def get_db_starred_sessions():
    """Get list of starred session IDs from database."""

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, tags, title FROM conversations WHERE is_starred = 1")
        rows = cursor.fetchall()
        conn.close()

        starred = {}
        for row in rows:
            starred[row['session_id']] = {
                'tags': row['tags'],
                'title': row['title']
            }
        return starred
    except:
        return {}

@app.route('/')
def index():
    """Serve the main HTML interface."""

    html_file = BASE_PATH / "assets" / "manager.html"
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            return render_template_string(f.read())
    return "Interface file not found. Please generate it first.", 404

@app.route('/api/conversations')
def get_conversations():
    """Get all conversations from jsonl files (real-time)."""

    # Get query parameters
    search = request.args.get('search', '').lower()
    project = request.args.get('project', '')
    tag = request.args.get('tag', '')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    # Get starred sessions from database
    starred_sessions = get_db_starred_sessions()

    # Scan all jsonl files
    jsonl_files = scan_jsonl_files()

    # Parse all files
    all_conversations = []
    for jsonl_file in jsonl_files:
        conv = parse_jsonl_file(jsonl_file)
        if conv:
            # Add starred info and custom tags/title from database
            session_id = conv['session_id']
            if session_id in starred_sessions:
                conv['is_starred'] = 1
                if starred_sessions[session_id]['tags']:
                    conv['tags'] = starred_sessions[session_id]['tags']
                if starred_sessions[session_id]['title']:
                    conv['title'] = starred_sessions[session_id]['title']
            else:
                conv['is_starred'] = 0
                conv['tags'] = conv.get('tags', '')

            all_conversations.append(conv)

    # Filter by search, project, tag
    filtered = []
    for conv in all_conversations:
        # Search filter
        if search:
            if search not in conv['title'].lower() and search not in conv['content'].lower():
                continue

        # Project filter
        if project:
            if conv['project_name'] != project:
                continue

        # Tag filter
        if tag:
            if not conv['tags'] or tag not in conv['tags']:
                continue

        filtered.append(conv)

    # Sort by created_at (newest first)
    filtered.sort(key=lambda x: x['created_at'], reverse=True)

    # Apply pagination
    total = len(filtered)
    paginated = filtered[offset:offset + limit]

    # Format for response
    conversations = []
    for conv in paginated:
        conversations.append({
            'id': conv['session_id'],  # Use session_id as id
            'title': conv['title'],
            'summary': conv['summary'],
            'tags': conv['tags'],
            'project_name': conv['project_name'],
            'created_at': conv['created_at'],
            'created_formatted': format_datetime(conv['created_at']),
            'is_starred': conv['is_starred'],
            'session_id': conv['session_id'],
            'version': 1,
            'message_count': conv['message_count']
        })

    return jsonify({
        'conversations': conversations,
        'total': total,
        'limit': limit,
        'offset': offset
    })

@app.route('/api/conversations/<int:conv_id>/related')
def get_related_conversations(conv_id):
    """Get related conversations (same project, tags, or session)."""

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get current conversation info
    cursor.execute("SELECT project_name, tags, session_id FROM conversations WHERE id = ?", (conv_id,))
    current = cursor.fetchone()

    if not current:
        conn.close()
        return jsonify([])

    related = []
    seen_ids = {conv_id}

    # Get conversations from same session (other versions)
    if current['session_id']:
        cursor.execute("""
            SELECT id, title, version, created_at
            FROM conversations
            WHERE session_id = ? AND id != ?
            ORDER BY version DESC
            LIMIT 5
        """, (current['session_id'], conv_id))
        for row in cursor.fetchall():
            if row['id'] not in seen_ids:
                related.append({
                    'id': row['id'],
                    'title': row['title'],
                    'relation': '同对话窗口',
                    'version': row['version'],
                    'created_formatted': format_datetime(row['created_at'])
                })
                seen_ids.add(row['id'])

    # Get conversations from same project
    if current['project_name']:
        cursor.execute("""
            SELECT id, title, created_at
            FROM conversations
            WHERE project_name = ? AND id != ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (current['project_name'], conv_id))
        for row in cursor.fetchall():
            if row['id'] not in seen_ids and len(related) < 8:
                related.append({
                    'id': row['id'],
                    'title': row['title'],
                    'relation': '同项目',
                    'created_formatted': format_datetime(row['created_at'])
                })
                seen_ids.add(row['id'])

    # Get conversations with same tags
    if current['tags']:
        tags = current['tags'].split(',')
        for tag in tags[:2]:  # Check first 2 tags
            cursor.execute("""
                SELECT id, title, created_at
                FROM conversations
                WHERE tags LIKE ? AND id != ?
                ORDER BY created_at DESC
                LIMIT 2
            """, (f"%{tag.strip()}%", conv_id))
            for row in cursor.fetchall():
                if row['id'] not in seen_ids and len(related) < 10:
                    related.append({
                        'id': row['id'],
                        'title': row['title'],
                        'relation': f'标签: {tag.strip()}',
                        'created_formatted': format_datetime(row['created_at'])
                    })
                    seen_ids.add(row['id'])

    conn.close()

    return jsonify(related[:10])

@app.route('/api/conversations/<int:conv_id>')
def get_conversation(conv_id):
    """Get single conversation by database ID (fallback for compatibility)."""

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Conversation not found'}), 404

    return jsonify({
        'id': row['id'],
        'title': row['title'],
        'summary': row['summary'],
        'content': row['content'],
        'tags': row['tags'],
        'project_name': row['project_name'],
        'created_at': row['created_at'],
        'created_formatted': format_datetime(row['created_at']),
        'is_starred': row['is_starred'] if row['is_starred'] is not None else 0,
        'session_id': row['session_id'],
        'version': row['version'] if row['version'] is not None else 1
    })

@app.route('/api/conversations/session/<session_id>', methods=['GET'])
def get_conversation_by_session(session_id):
    """Get conversation by session ID (reads directly from jsonl file)."""

    # Find the jsonl file for this session
    jsonl_files = scan_jsonl_files()
    target_file = None

    for jsonl_file in jsonl_files:
        if jsonl_file.stem == session_id:
            target_file = jsonl_file
            break

    if not target_file:
        return jsonify({'error': 'Conversation not found'}), 404

    # Parse the jsonl file
    conv = parse_jsonl_file(target_file)

    if not conv:
        return jsonify({'error': 'Failed to parse conversation'}), 404

    # Get starred info from database
    starred_sessions = get_db_starred_sessions()
    if session_id in starred_sessions:
        conv['is_starred'] = 1
        conv['tags'] = starred_sessions[session_id].get('tags', '')
        if starred_sessions[session_id].get('title'):
            conv['title'] = starred_sessions[session_id]['title']
    else:
        conv['is_starred'] = 0
        conv['tags'] = ''

    return jsonify({
        'id': session_id,
        'title': conv['title'],
        'summary': conv['summary'],
        'content': conv['content'],
        'tags': conv['tags'],
        'project_name': conv['project_name'],
        'created_at': conv['created_at'],
        'created_formatted': format_datetime(conv['created_at']),
        'is_starred': conv['is_starred'],
        'session_id': session_id,
        'version': 1,
        'message_count': conv['message_count'],
        'file_path': conv.get('file_path', str(target_file))  # 添加文件路径
    })

@app.route('/api/conversations/session/<session_id>', methods=['PUT'])
def update_conversation_by_session(session_id):
    """Update conversation metadata by session ID."""
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if conversation exists in database
    cursor.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()

    updates = []
    params = []

    if 'title' in data:
        updates.append("title = ?")
        params.append(data['title'])

    if 'summary' in data:
        updates.append("summary = ?")
        params.append(data['summary'])

    if 'tags' in data:
        updates.append("tags = ?")
        params.append(data['tags'])

    if 'project_name' in data:
        updates.append("project_name = ?")
        params.append(data['project_name'])

    if 'is_starred' in data:
        updates.append("is_starred = ?")
        params.append(1 if data['is_starred'] else 0)

    if updates:
        if row:
            # Update existing record
            params.append(session_id)
            cursor.execute(f"UPDATE conversations SET {', '.join(updates)} WHERE session_id = ?", params)
        else:
            # Insert new record (for starring)
            jsonl_files = scan_jsonl_files()
            target_file = None
            for jsonl_file in jsonl_files:
                if jsonl_file.stem == session_id:
                    target_file = jsonl_file
                    break

            if target_file:
                conv = parse_jsonl_file(target_file)
                if conv:
                    cursor.execute("""
                        INSERT INTO conversations (session_id, title, summary, content, project_name, created_at, message_count, is_starred, tags)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        data.get('title', conv['title']),
                        conv.get('summary', ''),
                        conv['content'],
                        conv['project_name'],
                        conv['created_at'],
                        conv['message_count'],
                        1 if data.get('is_starred') else 0,
                        data.get('tags', '')
                    ))

        conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/conversations/session/<session_id>', methods=['DELETE'])
def delete_conversation_by_session(session_id):
    """Delete conversation from database by session ID (source file not deleted)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'deleted_count': deleted_count})

@app.route('/api/export/session/<session_id>')
def export_conversation_by_session(session_id):
    """Export conversation as Markdown by session ID."""
    # Get conversation data
    jsonl_files = scan_jsonl_files()
    target_file = None

    for jsonl_file in jsonl_files:
        if jsonl_file.stem == session_id:
            target_file = jsonl_file
            break

    if not target_file:
        return jsonify({'error': 'Conversation not found'}), 404

    conv = parse_jsonl_file(target_file)
    if not conv:
        return jsonify({'error': 'Failed to parse conversation'}), 404

    # Get starred info from database
    starred_sessions = get_db_starred_sessions()
    if session_id in starred_sessions:
        conv['is_starred'] = 1
        conv['tags'] = starred_sessions[session_id].get('tags', '')
        if starred_sessions[session_id].get('title'):
            conv['title'] = starred_sessions[session_id]['title']
    else:
        conv['is_starred'] = 0
        conv['tags'] = ''

    # Generate Markdown
    md_content = f"# {conv['title']}\n\n"
    md_content += f"**时间:** {format_datetime(conv['created_at'])}\n"
    if conv['project_name']:
        md_content += f"**项目:** {conv['project_name']}\n"
    if conv['tags']:
        md_content += f"**标签:** {conv['tags']}\n"
    md_content += "\n"

    if conv.get('summary'):
        md_content += f"## 摘要\n\n{conv['summary']}\n\n"

    md_content += f"## 对话内容\n\n{conv['content']}"

    # Save to file
    from io import BytesIO
    buffer = BytesIO()
    buffer.write(md_content.encode('utf-8'))
    buffer.seek(0)

    filename = f"{conv['title']}_{format_datetime(conv['created_at'])}.md"
    filename = filename.replace(':', '-').replace(' ', '_').replace('/', '_')

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='text/markdown')

@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    """Delete a conversation."""

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/conversations/<int:conv_id>', methods=['PUT'])
def update_conversation(conv_id):
    """Update conversation metadata."""

    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if 'title' in data:
        updates.append("title = ?")
        params.append(data['title'])

    if 'summary' in data:
        updates.append("summary = ?")
        params.append(data['summary'])

    if 'tags' in data:
        updates.append("tags = ?")
        params.append(data['tags'])

    if 'project_name' in data:
        updates.append("project_name = ?")
        params.append(data['project_name'])

    if 'is_starred' in data:
        updates.append("is_starred = ?")
        params.append(1 if data['is_starred'] else 0)

    if updates:
        params.append(conv_id)
        cursor.execute(f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    conn.close()

    return jsonify({'success': True})

@app.route('/api/conversations/batch-delete', methods=['POST'])
def batch_delete_conversations():
    """Delete multiple conversations at once."""

    data = request.json
    ids = data.get('ids', [])

    if not ids:
        return jsonify({'error': 'No IDs provided'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join('?' * len(ids))
    cursor.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", ids)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'deleted_count': deleted_count})

@app.route('/api/export/<int:conv_id>')
def export_conversation(conv_id):
    """Export conversation as Markdown."""

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Conversation not found'}), 404

    # Generate Markdown
    md_content = f"# {row['title']}\n\n"
    md_content += f"**时间:** {format_datetime(row['created_at'])}\n"
    if row['project_name']:
        md_content += f"**项目:** {row['project_name']}\n"
    if row['tags']:
        md_content += f"**标签:** {row['tags']}\n"
    md_content += "\n"

    if row['summary']:
        md_content += f"## 摘要\n\n{row['summary']}\n\n"

    md_content += f"## 对话内容\n\n{row['content']}\n"

    # Save to file
    filename = f"conv_{conv_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = EXPORTS_DIR / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/api/stats')
def get_stats():
    """Get statistics from jsonl files."""

    # Scan all jsonl files
    jsonl_files = scan_jsonl_files()

    # Get starred sessions from database
    starred_sessions = get_db_starred_sessions()

    # Parse all files
    all_conversations = []
    for jsonl_file in jsonl_files:
        conv = parse_jsonl_file(jsonl_file)
        if conv:
            all_conversations.append(conv)

    # Count total
    total = len(all_conversations)

    # Count by project
    project_counts = {}
    for conv in all_conversations:
        project = conv['project_name']
        project_counts[project] = project_counts.get(project, 0) + 1

    projects = [{'name': p, 'count': c} for p, c in sorted(project_counts.items(), key=lambda x: x[1], reverse=True)]

    # Get tags from database (only starred sessions have tags)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM conversations WHERE tags IS NOT NULL")
    all_tags = {}
    for row in cursor.fetchall():
        for tag in row['tags'].split(','):
            tag = tag.strip()
            if tag:
                all_tags[tag] = all_tags.get(tag, 0) + 1
    conn.close()

    tags = [{'name': tag, 'count': count} for tag, count in sorted(all_tags.items(), key=lambda x: x[1], reverse=True)]

    # Recent activity (based on jsonl file modification times)
    activity = []
    # Simple implementation - just count by date from created_at
    date_counts = {}
    for conv in all_conversations:
        try:
            date_str = conv['created_at'][:10]  # YYYY-MM-DD
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
        except:
            pass

    activity = [{'date': d, 'count': c} for d, c in sorted(date_counts.items(), key=lambda x: x[0], reverse=True)[:7]]

    return jsonify({
        'total': total,
        'projects': projects,
        'tags': tags,
        'activity': activity
    })

@app.route('/api/projects')
def get_projects():
    """Get all unique project names from jsonl files."""

    # Scan all jsonl files
    jsonl_files = scan_jsonl_files()

    # Extract project names
    projects = set()
    for jsonl_file in jsonl_files:
        project_name = jsonl_file.parent.name
        projects.add(project_name)

    return jsonify(sorted(list(projects)))

@app.route('/api/tags')
def get_tags():
    """Get all unique tags from database (for starred/saved conversations)."""

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT tags FROM conversations WHERE tags IS NOT NULL")
        all_tags = set()
        for row in cursor.fetchall():
            for tag in row['tags'].split(','):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)

        conn.close()

        return jsonify(sorted(list(all_tags)))
    except:
        return jsonify([])

def run_server(port=5000):
    """Run the Flask server."""

    print(f"\n{'='*50}")
    print(f"  Claude Code历史对话管理系统")
    print(f"{'='*50}")
    print(f"\nWeb: http://localhost:{port}")
    print(f"Press Ctrl+C to stop\n")

    app.run(host='127.0.0.1', port=port, debug=False)

if __name__ == '__main__':
    run_server(13001)

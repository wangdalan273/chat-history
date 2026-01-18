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
    """Generate a smart title by analyzing conversation content."""

    import re
    from collections import Counter

    if not user_messages:
        return "对话记录"

    # Combine all user messages for analysis
    all_text = ' '.join(user_messages[:5])  # Analyze first 5 messages

    # Define topic keywords that indicate the conversation theme
    topic_keywords = {
        '功能开发': ['创建', '开发', '实现', '写', '生成', '添加', 'build', 'create', 'implement'],
        'Bug修复': ['修复', '解决', '报错', '错误', 'bug', 'error', 'fix', 'debug'],
        '代码优化': ['优化', '重构', '改进', 'improve', 'optimize', 'refactor'],
        '问题咨询': ['如何', '怎么', '怎样', '为什么', 'help', 'how', 'question'],
        '数据分析': ['分析', '统计', '数据', 'analyze', 'data', 'statistics'],
        '文档编写': ['文档', '说明', '注释', 'document', 'comment', 'readme'],
        '配置部署': ['配置', '部署', '安装', '环境', 'config', 'deploy', 'setup', 'install'],
        '界面设计': ['界面', 'UI', '页面', '样式', 'design', 'interface', 'style'],
        '算法实现': ['算法', '排序', '搜索', 'algorithm', 'sort', 'search'],
        '数据库': ['数据库', '查询', 'SQL', 'database', 'query', 'table'],
        'API开发': ['API', '接口', '请求', 'endpoint', 'request', 'interface'],
        '测试相关': ['测试', 'test', '单元测试', 'unit test'],
    }

    # Score each topic based on keyword matches
    topic_scores = {}
    for topic, keywords in topic_keywords.items():
        score = 0
        for keyword in keywords:
            score += all_text.lower().count(keyword.lower())
        if score > 0:
            topic_scores[topic] = score

    # Extract specific nouns/topics mentioned
    # Look for patterns like "XXX功能", "XXX问题", "XXX项目"
    specific_topics = []
    patterns = [
        r'([^，。！？\n]{2,10})(?:功能|项目|系统|模块)',
        r'(?:开发|实现|创建|设计)\s*([^，。！？\n]{2,15})',
        r'([^，。！？\n]{2,10})(?:问题|bug|错误)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, all_text)
        specific_topics.extend(matches)

    # Generate title
    if topic_scores:
        # Get the highest scoring topic
        main_topic = max(topic_scores, key=topic_scores.get)

        # Add specific topic if found
        if specific_topics:
            specific = specific_topics[0].strip()
            if len(specific) > 8:
                specific = specific[:8] + '...'
            title = f"{specific} - {main_topic}"
        else:
            title = main_topic
    elif specific_topics:
        title = specific_topics[0].strip()
        if len(title) > 15:
            title = title[:15] + '...'
    else:
        # Fallback: extract key phrase from first message
        first_msg = user_messages[0]
        # Remove common prefixes
        for prefix in ['帮我', '请', '可以', '我想要']:
            if first_msg.startswith(prefix):
                first_msg = first_msg[len(prefix):].strip()
                break

        # Get first meaningful phrase
        if len(first_msg) > 25:
            # Try to cut at a natural break
            for sep in ['，', '。', '！', '？', '\n', ' ', '的', '是']:
                if sep in first_msg[:25]:
                    first_msg = first_msg.split(sep)[0].strip()
                    break
            else:
                first_msg = first_msg[:25] + '...'
        title = first_msg

    return title if title else "对话记录"

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
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text':
                                        content_text.append(item.get('text', ''))
                                elif isinstance(item, str):
                                    content_text.append(item)
                            content = '\n'.join(content_text).strip()

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

@app.route('/api/conversations/session/<session_id>')
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
        if starred_sessions[session_id]['tags']:
            conv['tags'] = starred_sessions[session_id]['tags']
        if starred_sessions[session_id]['title']:
            conv['title'] = starred_sessions[session_id]['title']
    else:
        conv['is_starred'] = 0
        conv['tags'] = conv.get('tags', '')

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
        'message_count': conv['message_count']
    })

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

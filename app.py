import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, render_template_string

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)

# Use environment variables for configuration
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@123')
DEFAULT_USER_PASSWORD = os.environ.get('DEFAULT_USER_PASSWORD', 'User@123')

# In-memory storage (Vercel doesn't persist files)
# Note: This will reset on each deployment
users = {
    "admin": {
        "password": hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest(),
        "is_admin": True,
        "upload_limit": 100,
        "created_at": datetime.now().isoformat(),
        "last_login": None
    }
}

uploads = {}
running_bots = {}  # Note: Can't run actual processes on Vercel
settings = {
    "global_upload_limit": 10,
    "max_file_size": 5,  # MB (Vercel limit)
    "allowed_extensions": [".py", ".js", ".txt"],
    "session_timeout": 30
}

# HTML Templates (embedded for Vercel)
LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sulav Hosting - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 90%;
            max-width: 400px;
            padding: 40px;
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo h1 {
            font-size: 2rem;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 1rem;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .login-btn {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.3s;
        }
        .login-btn:hover {
            transform: translateY(-2px);
        }
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>Sulav Hosting</h1>
            <p>Vercel Edition</p>
        </div>
        
        <div id="errorMessage" class="error-message"></div>
        
        <form id="loginForm">
            <div class="form-group">
                <input type="text" id="username" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="password" id="password" placeholder="Password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
        </form>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();
                
                if (response.ok) {
                    window.location.href = data.redirect;
                } else {
                    document.getElementById('errorMessage').style.display = 'block';
                    document.getElementById('errorMessage').textContent = data.error;
                }
            } catch (error) {
                document.getElementById('errorMessage').style.display = 'block';
                document.getElementById('errorMessage').textContent = 'Login failed';
            }
        });
    </script>
</body>
</html>
'''

DASHBOARD_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sulav Hosting - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        }
        body {
            background: #f5f5f5;
        }
        .navbar {
            background: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .logout-btn {
            padding: 8px 15px;
            background: #f44336;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            padding: 0 2rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        .stat-card h3 {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 2rem;
            font-weight: bold;
            color: #333;
        }
        .section {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        .section-title {
            font-size: 1.3rem;
            color: #333;
            margin-bottom: 20px;
        }
        .upload-area {
            border: 2px dashed #667eea;
            border-radius: 10px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .upload-area:hover {
            background: #f8f9ff;
        }
        .file-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        .file-item {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 500;
            margin: 0 5px;
        }
        .btn-primary { background: #667eea; color: white; }
        .btn-success { background: #48bb78; color: white; }
        .btn-danger { background: #f56565; color: white; }
        .alert {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        .alert-success { background: #c6f6d5; color: #22543d; }
        .alert-error { background: #fed7d7; color: #742a2a; }
        .log-box {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 10px;
            font-family: monospace;
            height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="logo">Sulav Hosting</div>
        <div class="user-info">
            <span id="username"></span>
            <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
    </nav>

    <div class="container">
        <div id="alert" class="alert"></div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Files Uploaded</h3>
                <div class="value" id="uploadCount">0</div>
                <div id="uploadLimit"></div>
            </div>
            <div class="stat-card">
                <h3>Storage Used</h3>
                <div class="value" id="storageUsed">0 MB</div>
            </div>
        </div>

        <!-- Upload Section -->
        <div class="section">
            <h2 class="section-title">Upload Bot</h2>
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <p>Click to upload or drag and drop</p>
                <p class="small">Supported: .py, .js, .txt (Max: 5MB)</p>
                <input type="file" id="fileInput" style="display: none;" onchange="uploadFile()">
            </div>
        </div>

        <!-- Files Section -->
        <div class="section">
            <h2 class="section-title">My Files</h2>
            <div id="fileList" class="file-list">
                Loading files...
            </div>
        </div>

        <!-- Logs Section -->
        <div class="section">
            <h2 class="section-title">View Logs</h2>
            <select id="logFileSelect" style="width: 100%; padding: 10px; margin-bottom: 10px;">
                <option value="">Select a file</option>
            </select>
            <button class="btn btn-primary" onclick="loadLogs()">View Logs</button>
            <div id="logBox" class="log-box">
                Select a file to view logs
            </div>
        </div>
    </div>

    <script>
        let currentUser = null;

        document.addEventListener('DOMContentLoaded', () => {
            loadUserData();
        });

        async function loadUserData() {
            try {
                const response = await fetch('/api/user/stats');
                const data = await response.json();
                
                if (response.ok) {
                    currentUser = data;
                    document.getElementById('username').textContent = data.username;
                    document.getElementById('uploadCount').textContent = data.upload_count;
                    document.getElementById('uploadLimit').textContent = `Limit: ${data.upload_limit}`;
                    document.getElementById('storageUsed').textContent = formatSize(data.total_size || 0);
                    
                    loadFiles(data.uploads);
                    loadLogFileList(data.uploads);
                }
            } catch (error) {
                showAlert('Failed to load user data', 'error');
            }
        }

        function loadFiles(uploads) {
            if (!uploads || uploads.length === 0) {
                document.getElementById('fileList').innerHTML = '<p>No files uploaded yet.</p>';
                return;
            }
            
            let html = '';
            uploads.forEach(file => {
                html += `
                    <div class="file-item">
                        <div>
                            <strong>${file.filename}</strong><br>
                            <small>${formatSize(file.size)} • ${new Date(file.uploaded_at).toLocaleString()}</small>
                        </div>
                        <div>
                            <button class="btn btn-sm btn-danger" onclick="deleteFile('${file.filename}')">Delete</button>
                        </div>
                    </div>
                `;
            });
            
            document.getElementById('fileList').innerHTML = html;
        }

        function loadLogFileList(uploads) {
            let options = '<option value="">Select a file</option>';
            uploads?.forEach(file => {
                options += `<option value="${file.filename}">${file.filename}</option>`;
            });
            document.getElementById('logFileSelect').innerHTML = options;
        }

        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/api/user/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showAlert('File uploaded successfully!', 'success');
                    fileInput.value = '';
                    loadUserData();
                } else {
                    showAlert(data.error || 'Upload failed', 'error');
                }
            } catch (error) {
                showAlert('Upload failed', 'error');
            }
        }

        async function deleteFile(filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            
            try {
                const response = await fetch('/api/user/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ filename })
                });
                
                if (response.ok) {
                    showAlert('File deleted!', 'success');
                    loadUserData();
                }
            } catch (error) {
                showAlert('Delete failed', 'error');
            }
        }

        async function loadLogs() {
            const filename = document.getElementById('logFileSelect').value;
            if (!filename) {
                showAlert('Select a file', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/user/logs/${filename}`);
                const logs = await response.text();
                document.getElementById('logBox').textContent = logs || 'No logs available';
            } catch (error) {
                document.getElementById('logBox').textContent = 'Failed to load logs';
            }
        }

        function formatSize(bytes) {
            if (bytes === 0) return '0 B';
            const units = ['B', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
        }

        function showAlert(message, type) {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.className = `alert alert-${type}`;
            alert.style.display = 'block';
            setTimeout(() => alert.style.display = 'none', 3000);
        }

        function logout() {
            window.location.href = '/api/logout';
        }
    </script>
</body>
</html>
'''

# ==================== Helper Functions ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        if not users.get(session['user_id'], {}).get('is_admin', False):
            return jsonify({"error": "Admin required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# ==================== Routes ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login')
def login_page():
    return LOGIN_PAGE

@app.route('/dashboard')
@login_required
def dashboard():
    return DASHBOARD_PAGE

# ==================== API Routes ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = users.get(username)
    if user and user['password'] == hash_password(password):
        session.permanent = True
        session['user_id'] = username
        user['last_login'] = datetime.now().isoformat()
        return jsonify({
            'success': True,
            'redirect': '/dashboard'
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout')
def api_logout():
    session.clear()
    return redirect('/login')

@app.route('/api/user/stats')
@login_required
def user_stats():
    username = session['user_id']
    user_uploads = uploads.get(username, [])
    
    total_size = sum(u.get('size', 0) for u in user_uploads)
    
    return jsonify({
        'username': username,
        'is_admin': users.get(username, {}).get('is_admin', False),
        'upload_count': len(user_uploads),
        'upload_limit': users.get(username, {}).get('upload_limit', settings['global_upload_limit']),
        'total_size': total_size,
        'uploads': user_uploads
    })

@app.route('/api/user/upload', methods=['POST'])
@login_required
def user_upload():
    username = session['user_id']
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings['allowed_extensions']:
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check limit
    user_uploads = uploads.get(username, [])
    if len(user_uploads) >= users[username]['upload_limit']:
        return jsonify({'error': 'Upload limit reached'}), 400
    
    # Check size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > settings['max_file_size'] * 1024 * 1024:
        return jsonify({'error': f'Max size {settings["max_file_size"]}MB'}), 400
    
    # Store file content in memory (Vercel compatible)
    file_content = file.read()
    file_content_b64 = base64.b64encode(file_content).decode('utf-8')
    
    # Save to uploads
    if username not in uploads:
        uploads[username] = []
    
    uploads[username].append({
        'filename': file.filename,
        'uploaded_at': datetime.now().isoformat(),
        'size': file_size,
        'content': file_content_b64  # Store in memory
    })
    
    return jsonify({'success': True})

@app.route('/api/user/logs/<filename>')
@login_required
def user_logs(filename):
    username = session['user_id']
    user_uploads = uploads.get(username, [])
    
    # Find the file
    for upload in user_uploads:
        if upload['filename'] == filename:
            # Create a simple log entry
            log_content = f"""
{'='*50}
Bot Management Log
{'='*50}

File: {filename}
Uploaded: {upload['uploaded_at']}
Size: {upload['size']} bytes

{'='*50}
Status: File stored in memory (Vercel)
{'='*50}

Note: Actual bot execution is not available on Vercel.
This is a static hosting demonstration.
            """
            return log_content
    
    return 'No logs available', 404

@app.route('/api/user/delete', methods=['POST'])
@login_required
def user_delete():
    username = session['user_id']
    data = request.json
    filename = data.get('filename')
    
    if username in uploads:
        uploads[username] = [u for u in uploads[username] if u['filename'] != filename]
    
    return jsonify({'success': True})

# ==================== Vercel Handler ====================

# For Vercel serverless
def handler(event, context):
    return app

# For local development
if __name__ == '__main__':
    print("="*50)
    print("Sulav Hosting Panel - Vercel Edition")
    print("="*50)
    print("Default Admin: admin / Admin@123")
    print("Default User: user / User@123")
    print("="*50)
    print("Note: Running in local mode")
    print("="*50)
    
    # Add a default user for testing
    users["user"] = {
        "password": hash_password(DEFAULT_USER_PASSWORD),
        "is_admin": False,
        "upload_limit": 10,
        "created_at": datetime.now().isoformat(),
        "last_login": None
    }
    
    app.run(host='0.0.0.0', port=3000, debug=True)
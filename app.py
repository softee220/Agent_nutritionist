from flask import Flask, render_template, request, jsonify
import sys
import os
import json

# main_react.py가 있는 경로를 시스템 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# main_react.py에서 에이전트 실행 함수 import
try:
    from main_react import run_react_agent_once
except ImportError:
    # main_react.py가 없을 경우 더미 함수 사용 (테스트용)
    def run_react_agent_once(msg):
        return f"에이전트 응답 테스트: {msg}"

app = Flask(__name__)

# 데이터 파일이 위치한 로그 폴더 경로
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')

def read_json_file(filename):
    """로그 폴더에서 JSON 파일을 읽어옵니다."""
    try:
        path = os.path.join(LOG_DIR, filename)
        if not os.path.exists(path):
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return {}

def save_json_file(filename, data):
    """로그 폴더에 JSON 파일을 저장합니다."""
    try:
        path = os.path.join(LOG_DIR, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

def read_text_file(filename):
    """로그 폴더에서 텍스트 파일을 읽어옵니다."""
    try:
        path = os.path.join(LOG_DIR, filename)
        if not os.path.exists(path):
            return "기록된 데이터가 없습니다."
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return f"파일 읽기 오류: {e}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '')
    
    if not user_input:
        return jsonify({'error': 'No input provided'}), 400

    try:
        response_text = run_react_agent_once(user_input)
        return jsonify({'response': response_text})
    except Exception as e:
        print(f"Error executing agent: {e}")
        return jsonify({'error': str(e)}), 500

# --- 데이터 API 엔드포인트 ---

@app.route('/api/dashboard')
def get_dashboard_data():
    daily = read_json_file('daily.json')
    weekly = read_json_file('weekly.json')
    return jsonify({'daily': daily, 'weekly': weekly})

@app.route('/api/info', methods=['GET', 'POST'])
def handle_info():
    if request.method == 'POST':
        # 정보 업데이트 요청 처리
        try:
            new_data = request.json
            current_data = read_json_file('private.json')
            
            # 기존 데이터에 새로운 데이터 병합 (업데이트)
            current_data.update(new_data)
            
            if save_json_file('private.json', current_data):
                return jsonify({'status': 'success', 'data': current_data})
            else:
                return jsonify({'error': 'Failed to save file'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        # GET 요청 처리
        info = read_json_file('private.json')
        return jsonify(info)

@app.route('/api/log')
def get_log_data():
    content = read_text_file('nutrition.txt')
    return jsonify({'content': content})

if __name__ == '__main__':
    # 로그 폴더가 없으면 생성 (에러 방지)
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        
    app.run(debug=True, port=5000)
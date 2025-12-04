from flask import Flask, render_template, request, jsonify
import sys
import os

# main_react.py가 있는 경로를 시스템 경로에 추가 (필요시)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# main_react.py에서 에이전트 실행 함수 import
# 주의: main_react.py와 같은 폴더에 tool 폴더 등이 잘 위치해 있어야 합니다.
from main_react import run_react_agent_once

app = Flask(__name__)

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
        # main_react.py의 에이전트 실행 (결과 텍스트 반환)
        # run_react_agent_once 함수는 내부적으로 print를 많이 하지만,
        # 최종적으로 return final 하는 값을 받아와서 웹에 뿌려줍니다.
        response_text = run_react_agent_once(user_input)
        
        return jsonify({'response': response_text})
    except Exception as e:
        print(f"Error executing agent: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
# coding: utf-8
# Project: voice_select
# File: run_flak.py
# Author: dingming shi
# Date: 2025/5/20 16:47
# IDE: PyCharm

from flask import Flask, render_template, send_file, request, jsonify
from pathlib import Path
import os
import random
import shutil
import re
app = Flask(__name__)
root_path = Path(os.path.dirname(__file__))
origin_voice_path = Path(root_path) / "origin_voice"
character_voice_path = Path(root_path) / 'character_voice'
PER_PAGE = 10

###### 预览页和相关功能 ######
@app.route('/')
def homepage():
    # 首页
    tab_list = get_all_collect()
    return render_template('preview.html', tab_list=tab_list)

def get_all_collect():
    """ 仅获取所有的合集 """
    collection_map = []
    for collection in origin_voice_path.iterdir():
        if collection.is_dir():
            collection_map.append(collection.name)
    return collection_map

@app.route('/load-more', methods=['GET'])
def load_more():
    """ 懒加载 一次加载十条角色数据 """
    collection = request.args.get('collection')
    offset = int(request.args.get('offset', 1))
    limit = int(request.args.get('limit', 10))

    collection_path = origin_voice_path / collection
    all_characters = [c for c in collection_path.iterdir() if c.is_dir()]
    all_characters.sort()

    start = (offset - 1) * limit
    end = start + limit
    sliced_characters = all_characters[start:end]
    role_map = []

    for character in sliced_characters:
        wavs = list(character.rglob("*.wav"))
        if not wavs:
            continue
        preview_audio = random.choice(wavs)
        role_map.append({
            character.name: {
                'count': len(wavs),
                'preview': str(preview_audio),
                'collect_name': collection
            }
        })

    return jsonify({'character_files': role_map, 'has_more': end < len(all_characters)})

@app.route('/create-character', methods=['POST'])
def create_character():
    """ 使用旧音源创建新角色 """
    data = request.get_json()
    path = data.get('path')  # 格式类似于 tab_li\character
    new_name = data.get('new_name')

    # 在这里调用你的逻辑，例如创建新角色
    collect, character = path.split('_')
    old_character_path = origin_voice_path / collect / character
    new_character_path = character_voice_path / new_name
    if os.path.exists(new_character_path):
        return jsonify({'status': 'fail', 'message': '角色创建失败 角色已存在'})
    if not os.path.exists(old_character_path):
        return jsonify({'status': 'fail', 'message': '角色创建失败 原始角色不存在'})

    os.makedirs(new_character_path, exist_ok=True)
    for item in os.listdir(old_character_path):
        src_path = os.path.join(old_character_path, item)
        dst_path = os.path.join(new_character_path, item)

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)  # 递归复制文件夹
        else:
            shutil.copy2(src_path, dst_path)
    # 示例返回
    return jsonify({'status': 'success', 'message': '角色创建成功'})

@app.route('/api/get_new_voice')
def get_new_voice():
    """ 随机获取指定角色下的一条语音 """
    path = request.args.get('path')
    collect, character = path.split('_')
    old_character_path = origin_voice_path / collect / character
    all_wav_files = list(old_character_path.rglob("*.wav"))

    if not all_wav_files:
        return jsonify({"error": "没有找到语音文件"}), 404

    random_wav = random.choice(all_wav_files)
    return jsonify({"new_filename": str(random_wav)})

###### 角色页和相关功能 ######

@app.route('/character_page')
def character_page():
    # 角色编辑页
    character_dict = collect_all_audio_by_character_voice()
    return render_template('character_page.html', character_dict=character_dict)

def collect_all_audio_by_character_voice():
    """ 搜集所有角色声音目录下的 角色 和 情绪"""
    role_map = {}
    for character in character_voice_path.iterdir():
        if character.is_dir():
            emotion_list = []
            for emotion in character.iterdir():
                if emotion.is_dir():
                    emotion_list.append(emotion.name)
            if emotion_list:
                role_map[character.name] = emotion_list
    return role_map

@app.route('/get_emotion_audio')
def get_emotion_audio():
    """
    根据情感表达获取所有对应情感的声音文件
    分页获取
    """
    character = request.args.get('character')
    emotion = request.args.get('emotion')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 10))
    collect = request.args.get('collect', '')

    if not collect:
        find_path = character_voice_path / character / emotion
    else:
        find_path = origin_voice_path / collect /character / emotion

    try:
        audio_files = find_path.rglob('*.wav')
        audio_list = []
        if audio_files:
            audio_list = [str(a) for a in audio_files]
            start = (page - 1) * page_size
            end = start + page_size
            page_files = audio_list[start:end]
        return jsonify({'audio_files': page_files, 'has_more': end < len(audio_list)})
    except Exception as e:
        return jsonify({'audio_files': [], 'error': str(e)})

@app.route('/voice')
def serve_voice():
    # 获取 URL 参数，例如 filename=原神/七七/中立_neutral/xxx.wav
    filepath = request.args.get('filename')
    if not filepath:
        return "Missing filename", 400

    # 拼接你的本地实际路径（注意安全检查）
    full_path = os.path.join("origin_voice", filepath)

    if not os.path.isfile(full_path):
        return "File not found", 404

    return send_file(full_path)

@app.route('/delete_character', methods=['POST'])
def delete_character():
    """ 删除角色 """
    data = request.get_json()
    character = data.get('character')

    if not character:
        return jsonify(success=False, error="缺少角色名")

    try:
        delete_path = character_voice_path / character
        shutil.rmtree(delete_path)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route('/add_emotion', methods=['POST'])
def add_emotion():
    """ 新增角色的情绪 """
    data = request.get_json()
    character = data.get('character', '').strip()
    collect = data.get('collect', '').strip()
    name = data.get('name', '').strip()

    if not collect:
        current_character_path = character_voice_path / character
    else:
        current_character_path = origin_voice_path / collect / character
    emotion_dict  = [p.name for p in current_character_path.iterdir() if p.is_dir()]
    if not name:
        return jsonify(success=False, error='角色名不能为空')

    if re.search(r'[\\/:*?"<>|]', name):
        return jsonify(success=False, error="情绪名称包含非法字符")

    if name in emotion_dict:
        return jsonify(success=False, error='情绪已存在')

    target_folder = current_character_path / name
    target_folder.mkdir(parents=True, exist_ok=True)
    return jsonify(success=True)

@app.route('/del_emotion', methods=['POST'])
def del_emotion():
    """ 删除角色的情绪 """
    data = request.get_json()
    character = data.get('character', '').strip()
    emotion = data.get('emotion', '').strip()
    collect = data.get('collect', '')

    if not character:
        current_character_path = character_voice_path / character
    else:
        current_character_path = origin_voice_path / collect / character

    if not emotion or not character:
        return jsonify(success=False, error='角色或情绪不能为空')

    target_folder = current_character_path / emotion
    if not target_folder.exists() or not target_folder.is_dir():
        return jsonify(success=False, error=f'目标情绪不存在：{target_folder}')

    shutil.rmtree(target_folder)
    return jsonify(success=True)

@app.route('/modify_emotion', methods=['POST'])
def modify_emotion():
    """ 修改情绪 """
    data = request.get_json()
    file = data.get('file', '')
    emotion_type = data.get('emotion_type', '')
    emotion_text = data.get('emotion_text', '').strip()
    emotion_text_ext = data.get('emotion_text_ext', '').strip()
    try:
        if not all([file, emotion_type, emotion_text, emotion_text_ext]):
            return jsonify(success=False, error="缺少必传参数")

        if re.search(r'[\\/:*?"<>|.]', emotion_text):
            return jsonify(success=False, error="情绪文本包括非法字符")

        source_path = Path(file)
        file_name = '.'.join([emotion_text, emotion_text_ext])
        destination_dir = source_path.parent.parent / emotion_type / file_name
        shutil.move(source_path, destination_dir)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

###### 源文件角色页编辑 ######
@app.route('/origin_page')
def origin_page():
    file = request.args.get('file')
    if not file:
        return "Missing 'file' parameter", 400

    try:
        collect, character = file.split('_')
        role_map = {}
        character = origin_voice_path / collect / character
        if character.is_dir():
            emotion_list = []
            for emotion in character.iterdir():
                if emotion.is_dir():
                    emotion_list.append(emotion.name)
            if emotion_list:
                role_map[character.name] = emotion_list

    except ValueError:
        return "Invalid 'file' format", 400

    return render_template('origin_page.html', collect=collect, character_dict=role_map)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
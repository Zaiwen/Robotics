"""
=====================================================
农业病虫害识别系统 - Flask 后端主程序
=====================================================
功能：
1. 提供前端页面服务
2. 接收图片和问题，调用大模型 API
3. 返回识别结果（JSON 格式）

运行方式：
    python app.py

访问地址：
    http://127.0.0.1:5000
"""

# ==================== 导入必要的库 ====================
from flask import Flask, render_template_string, request, jsonify
from werkzeug.utils import secure_filename
import os
import io
import base64
import json
import re
import importlib
from datetime import datetime

# 可选加载 .env，未安装 python-dotenv 时自动跳过。
try:
    dotenv_module = importlib.import_module("dotenv")
    load_dotenv = getattr(dotenv_module, "load_dotenv", None)
    if callable(load_dotenv):
        load_dotenv()
except Exception:
    pass

# ==================== Flask 应用初始化 ====================
# 创建 Flask 应用实例
app = Flask(__name__)

# 配置允许的上传文件大小（这里设置为 50MB）
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# 定义允许的文件扩展名
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}

PROVIDER_ALIASES = {
    'doubao': 'doubao',
    'ark': 'doubao',
    'openai': 'openai',
    'melon': 'melon_llm',
    'melon_llm': 'melon_llm',
    'melon_pest_disease_llm': 'melon_llm',
    'rice': 'rice_llm',
    'rice_llm': 'rice_llm',
    'longhao': 'rice_llm',
    'rice_pest_disease_llm': 'rice_llm'
}

SUPPORTED_PROVIDERS = {'doubao', 'openai', 'melon_llm', 'rice_llm'}

CROP_KEYWORDS = {
    'melon': ['甜瓜', '哈密瓜', '香瓜', 'melon', 'cucumis melo'],
    'rice': ['水稻', '稻', 'rice', 'paddy']
}

# ==================== 工具函数 ====================


def normalize_provider_name(provider_name):
    """将各种别名统一为内部 provider 名称。"""
    normalized = (provider_name or '').strip().lower()
    if not normalized:
        return ''
    return PROVIDER_ALIASES.get(normalized, normalized)


def ensure_supported_provider(provider_name, fallback='doubao'):
    """若 provider 非法则回退到 fallback。"""
    normalized = normalize_provider_name(provider_name)
    if normalized in SUPPORTED_PROVIDERS:
        return normalized
    fallback_normalized = normalize_provider_name(fallback) or 'doubao'
    return fallback_normalized if fallback_normalized in SUPPORTED_PROVIDERS else 'doubao'


def detect_crop_type(crop_type):
    """根据前端传参或问题文本判断作物类型。"""
    normalized_crop = (crop_type or '').strip().lower()

    return normalized_crop

def allowed_file(filename):
    """
    检查文件名是否合法
    参数：filename - 文件名字符串
    返回： bool - 是否合法
    """
    # 检查文件是否有扩展名且扩展名在允许列表中
    # '.' in filename and filename.rsplit('.', 1)[1].lower() 获取扩展名并转换为小写
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def encode_image_to_base64(image_bytes):
    """
    将图片字节数据编码为 Base64 字符串
    这样可以在 API 请求中传输二进制数据
    
    参数：image_bytes - 图片的二进制字节数据
    返回：str - Base64 编码的字符串
    """
    return base64.b64encode(image_bytes).decode('utf-8')


# ==================== 病虫害文本匹配简单函数 ====================

def analyze_with_llm_mock(image_bytes, user_question):
    """
    【模拟版本】使用大模型进行病虫害识别
    
    这是一个完全本地的"模拟"版本，不需要真实 API 密钥，方便快速测试。
    稍后可以替换为真实的大模型 API 调用。
    
    参数：
        image_bytes - 图片的二进制数据
        user_question - 用户输入的问题文本
    
    返回：
        dict - 包含识别结果的字典，格式为：
        {
            "disease_name": "病虫害名称",
            "reason": "判断依据",
            "advice": "防治建议",
            "warning": "风险提示"
        }
    """
    
    # 这里是一个简单的规则匹配逻辑，用于演示
    # 实际应用中，这里应该是真实的 API 调用
    
    # 将图片数据转为 base64（方便在日志中查看）
    image_base64 = encode_image_to_base64(image_bytes)
    print(f"[DEBUG] 已接收图片数据，大小: {len(image_bytes)} 字节")
    
    # 根据用户问题进行简单的关键词匹配
    question_lower = user_question.lower()
    
    # 定义一些常见的病虫害识别规则（演示用）
    recognition_rules = {
        '白粉病': {
            'keywords': ['白色', '白粉', 'powder'],
            'reason': '叶片表面出现白色粉状物，这是白粉病的典型特征。',
            'advice': '及时剪除病叶、改善通风条件；可用硫磺粉或对应杀菌剂喷雾。',
            'warning': '白粉病会严重降低光合作用效率，导致减产，请及时处理。'
        },
        '蚜虫': {
            'keywords': ['虫', '蚜虫', 'aphid', '绿', '卷叶'],
            'reason': '可见绿色或黑色小虫聚集，叶片卷曲变形，是蚜虫的典型症状。',
            'advice': '使用杀虫剂喷雾（如吡虫啉）；生物防治：引入瓢虫天敌。',
            'warning': '蚜虫繁殖快，可在短时间内造成大量危害，需尽快处理。'
        },
        '炭疽病': {
            'keywords': ['黑斑', '褐色', 'anthracnose', '坏死'],
            'reason': '叶片或果实上出现褐色或黑色坏死斑，中央常有浓色圆环。',
            'advice': '剪除病叶病果，烧毁处理；喷施铜基杀菌剂或代森锌。',
            'warning': '炭疽病会导致果实腐烂，严重影响商品价值，需立即防治。'
        },
        '红蜘蛛': {
            'keywords': ['红', '蜘蛛', 'spider', '叶片泛黄', '细丝'],
            'reason': '叶片褪色泛黄，背面可见细微丝网和红色小虫。',
            'advice': '增加环境湿度；使用杀螨剂（如虫螨克）或硫磺悬浮液。',
            'warning': '红蜘蛛易形成群体爆发，对高温干旱环境适应性强。'
        }
    }
    
    # 遍历规则，找到匹配的病虫害
    # 这里的逻辑非常简单，仅供演示。实际应用中应该使用更复杂的模型分析图片和文本。
    # 仅仅通过文本匹配是不够的？？？
    matched_disease = None
    for disease_name, disease_info in recognition_rules.items():
        for keyword in disease_info['keywords']:
            if keyword in question_lower:
                matched_disease = disease_name
                break
        if matched_disease:
            break
    
    # 如果没有匹配，返回通用结果
    # 感觉没用？？？
    if matched_disease:
        disease_info = recognition_rules[matched_disease]
        result = {
            "disease_name": matched_disease,
            "reason": disease_info['reason'],
            "advice": disease_info['advice'],
            "warning": disease_info['warning']
        }
    else:
        # 默认返回通用回复
        result = {
            "disease_name": "可能的病虫害（需验证）",
            "reason": "基于您上传的图片和描述，初步分析可能涉及的病虫害类别。由于本系统当前处于原型阶段，建议与专业农学工作者确认。",
            "advice": f"根据您的描述（'{user_question}'），建议：\n1. 拍照上传清晰的病患部位图片\n2. 详细描述症状（颜色、形状、位置等）\n3. 提供甜瓜生长阶段等背景信息\n4. 建议咨询农业专家进行确诊",
            "warning": "本系统仅作为辅助诊断工具，结果仅供参考。任何防治措施应在专业人士指导下进行。请勿过度使用农药。"
        }
    
    return result

# ==================== LLM 大模型 API 调用函数 ====================

def analyze_with_real_api(image_bytes, user_question, api_provider='doubao'):
    """
    使用真实大模型 API 进行病虫害识别。

    支持 provider:
    - doubao
    - openai
    - melon_llm（甜瓜专用，OpenAI 兼容）
    """
    provider = normalize_provider_name(api_provider)

    if provider == 'doubao':
        api_key = os.getenv('DOUBAO_API_KEY', '').strip() or os.getenv('ARK_API_KEY', '').strip()
        base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3').strip()
        model = os.getenv('DOUBAO_MODEL', 'doubao-seed-2-0-pro-260215').strip()
        if not api_key:
            raise ValueError("未检测到 DOUBAO_API_KEY（或 ARK_API_KEY），请先设置环境变量")
    elif provider == 'openai':
        api_key = os.getenv('OPENAI_API_KEY', '').strip()
        base_url = os.getenv('OPENAI_BASE_URL', '').strip()
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip()
        if not api_key:
            raise ValueError("未检测到 OPENAI_API_KEY，请先设置环境变量")
    elif provider == 'melon_llm':
        api_key = os.getenv('MELON_LLM_API_KEY', '').strip()
        base_url = os.getenv('MELON_LLM_BASE_URL', '').strip()
        model = os.getenv('MELON_LLM_MODEL', '').strip()
        if not api_key or not base_url or not model:
            raise ValueError("甜瓜模型未配置完整，请设置 MELON_LLM_API_KEY / MELON_LLM_BASE_URL / MELON_LLM_MODEL")
    else:
        raise ValueError("api_provider 不受支持，请使用 doubao/openai/melon_llm")

    try:
        openai_module = importlib.import_module("openai")
        OpenAI = getattr(openai_module, "OpenAI")
    except ImportError as exc:
        raise RuntimeError("未安装 openai SDK，请运行: pip install openai") from exc

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    system_prompt = (
        "你是一位资深的农业病虫害诊断专家。"
        "请根据作物病虫害图片和用户描述，输出 JSON，字段必须包含："
        "disease_name, reason, advice, warning。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"用户问题：{user_question}\n"
                        "请仅返回 JSON，字段包含 disease_name, reason, advice, warning。"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages
        )
    except Exception:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=messages
        )

    result_text = (response.choices[0].message.content or "{}").strip()
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', result_text)
        if not match:
            raise ValueError("模型返回内容不是合法 JSON，请检查模型配置或提示词")
        result = json.loads(match.group(0))

    return {
        "disease_name": result.get("disease_name", "未知病虫害"),
        "reason": result.get("reason", "模型未提供判断依据"),
        "advice": result.get("advice", "模型未提供防治建议"),
        "warning": result.get("warning", "模型未提供风险提示")
    }


@app.after_request
def add_cors_headers(response):
    """允许跨域访问，便于从 file:// 或其他本地端口调试前端。"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    return response


# ==================== Flask 路由 ====================

@app.route('/')
def Robotics_Web():
    """
    主页路由 - 按候选文件顺序读取前端页面
    如果想简化部署，也可以在这里直接返回 HTML 字符串
    """
    page = 'Robotics_Web_ps.html'


    try:
        if os.path.exists(page):
            with open(page, 'r', encoding='utf-8') as f:
                return f.read()

        raise FileNotFoundError("未找到任何可用主页文件")
    except FileNotFoundError:
        return jsonify({
            "error": "主页文件不存在。请确保 Robotics Web 3.0更新之后.html 或 model_others_new.html 与 app.py 在同一目录。"
        }), 404


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    主要的识别接口
    
    接收：
        - image: 上传的图片文件
        - question: 用户输入的问题文本
    
    返回：
        JSON 格式的识别结果
    """
    
    try:
        # ========== 验证请求数据 ==========
        
        # 检查是否有图片文件
        # request.files 是 Flask 提供的一个字典对象，包含了所有上传的文件。'image' 是前端上传文件时使用的字段名。
        if 'image' not in request.files:
            return jsonify({
                "success": False,
                "error": "请上传一张图片"
            }), 400
        
        image_file = request.files['image']
        
        # 检查是否选择了文件
        if image_file.filename == '':
            return jsonify({
                "success": False,
                "error": "请选择一张图片"
            }), 400
        
        # 检查文件扩展名是否合法
        if not allowed_file(image_file.filename):
            return jsonify({
                "success": False,
                "error": "只支持 JPG / PNG 格式的图片"
            }), 400
        
        # 检查是否有问题文本
        user_question = request.form.get('question', '').strip()
        if not user_question:
            return jsonify({
                "success": False,
                "error": "请输入问题或症状描述"
            }), 400
        
        # ========== 读取图片数据 ==========
        # 将上传的文件读取为二进制字节数据
        image_bytes = image_file.read()
        
        # 验证图片文件大小,之前又可以上传50MB的，这里怎么只有10MB了？？？感觉有点矛盾？？？
        max_image_size = 10 * 1024 * 1024  # 10MB
        if len(image_bytes) > max_image_size:
            return jsonify({
                "success": False,
                "error": "图片文件过大，请选择小于 10MB 的文件"
            }), 400
        
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 接收到识别请求")
        print(f"  - 文件名: {image_file.filename}")
        print(f"  - 文件大小: {len(image_bytes)} 字节")
        print(f"  - 用户问题: {user_question[:100]}...")  # 只打印前 100 个字符
        
        # ==========确定对应变量 ==========
        use_mock = request.form.get('use_mock', '0').strip() == '1'
        crop_type = request.form.get('crop_type', 'auto').strip().lower()

        # ========== 从这里开始分支melon_API/doubao ==========

        # default_provider = doubao
        default_provider = ensure_supported_provider(
            os.getenv('DEFAULT_API_PROVIDER', 'doubao').strip() or 'doubao'
        )


        # melon_provider = melon_llm
        melon_provider = ensure_supported_provider(
            os.getenv('MELON_PEST_DISEASE_LLM', 'melon_llm').strip() or 'melon_llm'
            , fallback=default_provider
        )
        


        # 感觉这句话是一个废话，是不需要识别的
        detected_crop = detect_crop_type(crop_type)

        if detected_crop == 'melon':
            primary_provider = melon_provider
            route_strategy = 'melon_route'
        else:
            primary_provider = default_provider
            route_strategy = 'default_route'

        attempted_providers = []

        try:
            if use_mock:
                result = analyze_with_llm_mock(image_bytes, user_question)
                provider_used = 'mock'
            else:
                provider_queue = [primary_provider]
                if default_provider not in provider_queue:
                    provider_queue.append(default_provider)

                model_errors = []
                result = None
                provider_used = None

                for provider in provider_queue:
                    attempted_providers.append(provider)
                    try:
                        result = analyze_with_real_api(image_bytes, user_question, api_provider=provider)
                        provider_used = provider
                        break
                    except Exception as provider_error:
                        model_errors.append(f"{provider}: {provider_error}")

                if result is None:
                    raise ValueError("所有候选模型调用失败: " + ' | '.join(model_errors))
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "attempted_providers": attempted_providers,
                "crop_type_detected": detected_crop,
                "route_strategy": route_strategy
            }), 400
        except RuntimeError as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "attempted_providers": attempted_providers,
                "crop_type_detected": detected_crop,
                "route_strategy": route_strategy
            }), 500
        
        # ========== 返回识别结果 ==========
        return jsonify({
            "success": True,
            "disease_name": result.get("disease_name", "-"),
            "reason": result.get("reason", "-"),
            "advice": result.get("advice", "-"),
            "warning": result.get("warning", "-"),
            "provider_used": provider_used,
            "attempted_providers": attempted_providers,
            "crop_type_detected": detected_crop,
            "route_strategy": route_strategy
        })
    
    except Exception as e:
        # 捕获任何异常并返回错误信息
        print(f"[ERROR] 处理请求时出错: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"服务器内部错误: {str(e)}"
        }), 500


# ==================== 健康检查接口 ==========

@app.route('/health')
def health():
    """
    健康检查接口
    用于检测服务是否正常运行
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Agriculture Disease Recognition System"
    })


# ==================== 错误处理 ==========

@app.errorhandler(404)
def page_not_found(e):
    """处理 404 错误"""
    return jsonify({
        "error": "请求的资源不存在",
        "status_code": 404
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """处理 500 错误"""
    return jsonify({
        "error": "服务器内部错误",
        "status_code": 500
    }), 500


# ==================== 应用启动 ==========

if __name__ == '__main__':
    """
    启动 Flask 应用
    
    参数说明：
    - debug=True: 启用调试模式（开发时使用）
    - host='127.0.0.1': 只在本地访问
    - port=5000: 监听端口号
    
    如果要允许其他设备访问，改为：
    - host='0.0.0.0'（但要注意安全性）
    """
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║   农业病虫害智能识别系统 - Flask 后端                        ║
    ╠════════════════════════════════════════════════════════════╣
    ║   现在运行中...                                             ║
    ║   访问地址: http://127.0.0.1:5000                           ║
    ║   按 Ctrl+C 停止服务                                        ║
    ╚════════════════════════════════════════════════════════════╝
    """)


    # 启动 Flask 应用
    app.run(debug=True, host='127.0.0.1', port=5000)

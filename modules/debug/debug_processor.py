import asyncio
import json
import jsbeautifier
import gc
from typing import Dict, List, Optional, Any
from modules.utils import get_cached_script_source, set_cached_script_source, measure_time
from modules.memory_manager import memory_manager, process_in_chunks


async def set_xhr_breakpoint(client, xhr_url="*"):
    """设置XHR请求断点
    
    Args:
        client: CDP客户端会话
        xhr_url: 要监听的XHR请求URL，默认为"*"表示监听所有XHR请求
        
    注意:
        - 当XHR请求匹配指定URL时，浏览器会暂停JavaScript执行
        - 空字符串或"*"表示监听所有XHR请求
        - URL可以是部分匹配，不需要完全一致
    """
    # 通过CDP命令设置XHR断点
    client.send("DOMDebugger.setXHRBreakpoint", {"url": xhr_url})
    print(f"✅ 已设置XHR断点，监听URL: {xhr_url if xhr_url else '所有XHR请求'}")
    # 注意：此函数不等待断点触发，只是设置断点

async def set_xhr_new_breakpoint(client, xhr_url, js_ready_event=None):
    """等待XHR断点触发并设置新的JS断点
    
    此函数实现了一个高级功能：当XHR断点触发时，自动在触发位置设置一个新的JS断点，
    然后移除原始XHR断点，并通知调试器可以开始监听新设置的JS断点。
    
    Args:
        client: CDP客户端会话
        xhr_url: 要监听的XHR请求URL
        js_ready_event: 可选的事件对象，用于通知调试器JS断点已准备就绪
        
    Returns:
        无返回值，但会设置js_ready_event事件（如果提供）
        
    Raises:
        Exception: 在断点处理过程中发生错误时抛出异常
    """
    print("等待XHR断点触发...")

    # 创建Future对象，用于异步等待断点触发事件
    event_future = asyncio.get_event_loop().create_future()

    # 定义断点暂停事件处理函数
    def paused_handler(event):
        # 只有在Future未完成时才设置结果，防止多次触发
        if not event_future.done():
            event_future.set_result(event)

    try:
        # 注册Debugger.paused事件监听器
        client.on('Debugger.paused', paused_handler)
        
        # 等待XHR断点触发
        try:
            # 阻塞等待，直到断点被触发
            event = await event_future
            print("XHR断点已触发！")
        except Exception as e:
            print(f"等待XHR断点触发时出错: {e}")
            raise

        # 分析断点触发位置的调用堆栈
        call_stack = event['callFrames']
        top_call = call_stack[-1]  # 获取最顶层堆栈帧（实际执行位置）

        # 提取断点位置信息
        location = top_call['location']
        script_id = location['scriptId']  # 脚本ID
        line_number = location['lineNumber']  # 行号（0-based）
        column_number = location['columnNumber']  # 列号（0-based）

        # 在当前位置设置新的JS断点
        try:
            await client.send("Debugger.setBreakpoint", {
                "location": {
                    "scriptId": script_id,
                    "lineNumber": line_number,
                    "columnNumber": column_number
                }
            })
            # 显示行号时+1转换为1-based（用户友好的行号）
            print(f"✅ 已在顶层调用堆栈位置设置新的JS断点: 行 {line_number + 1}, 列 {column_number + 1}")
        except Exception as e:
            print(f"设置JS断点时出错: {e}")
            raise

        # 移除原始XHR断点，避免重复触发
        try:
            await client.send("DOMDebugger.removeXHRBreakpoint", {"url": xhr_url})
            print("✅ 已移除XHR断点")
        except Exception as e:
            print(f"移除XHR断点时出错: {e}")
            # 继续执行，不中断流程

        print("✅ 已完成XHR断点处理并设置新JS断点，请重新执行操作触发断点")
        
        # 恢复执行以触发新设置的JS断点
        try:
            await client.send("Debugger.resume")
            print("✅ 已恢复执行，等待新设置的JS断点触发")
        except Exception as e:
            print(f"恢复执行时出错: {e}")
            # 仍然设置事件，让AI调试器继续

        # 通知continuous_debugging可以开始等待JS断点事件了
        if js_ready_event:
            js_ready_event.set()
            
    except Exception as e:
        print(f"XHR断点处理过程中发生错误: {e}")
        raise
    finally:
        # 确保总是移除事件监听器，防止内存泄漏
        client.remove_listener('Debugger.paused', paused_handler)


async def set_breakpoint(client, url_or_regex, line_number=0, column_number=0, condition="", is_regex=False):
    """在指定URL或匹配正则表达式的JavaScript文件中设置断点
    
    Args:
        client: CDP客户端会话
        url_or_regex: JavaScript文件的URL或URL正则表达式
        line_number: 断点行号（0-based，显示时会+1）
        column_number: 断点列号（0-based，显示时会+1）
        condition: 可选的断点条件表达式，只有表达式为true时断点才会触发
        is_regex: 是否将url_or_regex作为正则表达式处理
        
    Returns:
        dict: 包含断点ID和实际位置的结果对象
        
    Raises:
        Exception: 设置断点失败时抛出异常，但会被捕获并打印错误信息
    """
    try:
        # 根据is_regex参数决定使用urlRegex还是url参数
        if is_regex:
            # 使用正则表达式匹配URL
            result = await client.send("Debugger.setBreakpointByUrl", {
                "urlRegex": url_or_regex,  # URL正则表达式
                "lineNumber": line_number,  # 行号（0-based）
                "columnNumber": column_number,  # 列号（0-based）
                "condition": condition  # 断点条件
            })
            # 显示行号和列号时+1转换为1-based（用户友好的行列号）
            print(f"✅ 已通过正则 {url_or_regex} 在行 {line_number+1}, 列 {column_number+1} 设置断点")
        else:
            # 使用精确URL匹配
            result = await client.send("Debugger.setBreakpointByUrl", {
                "url": url_or_regex,  # 精确URL
                "lineNumber": line_number,  # 行号（0-based）
                "columnNumber": column_number,  # 列号（0-based）
                "condition": condition  # 断点条件
            })
            # 显示行号和列号时+1转换为1-based（用户友好的行列号）
            print(f"✅ 已在 {url_or_regex}, 行 {line_number+1}, 列 {column_number+1} 设置断点")
        return result
    except Exception as e:
        print(f"❌ 设置断点失败: {e}")
        # 返回None表示设置失败
        return None

def should_skip_property(name: str, value_obj: dict) -> bool:
    """判断属性是否应被跳过（跳过不必要的数据）"""
    if value_obj is None:
        return True
    if not name:
        return True
    if name == "this" or name.startswith('$'):
        return True
    description = value_obj.get("description", "")
    if description in ("Window", "global", "VueComponent", "HTMLDivElement", "HTMLElement", "options"):
        return True
    if description == "Object" and value_obj.get("className") == "Object" and value_obj.get("subtype") == "object":
        preview = value_obj.get("preview", {})
        properties = preview.get("properties", [])
        if len(properties) <= 5:
            return False
        return True
    if value_obj.get("type") == "function":
        return True
    if "Vue" in description or "Window" in description:
        return True
    if ("value" in value_obj and value_obj["value"] is None) or \
       ("description" in value_obj and value_obj["description"] == "null") or \
       name in {"constructor", "prototype", "$super", "__proto__", "window", "document", "location"}:
        return True
    return False

async def get_script_source(client, script_id: str) -> str:
    """
    统一获取脚本源代码，首先检查缓存，若无则通过 CDP 命令获取并缓存。
    """
    cached_source = get_cached_script_source(script_id)
    if cached_source is not None:
        return cached_source
    try:
        response = await client.send("Debugger.getScriptSource", {"scriptId": script_id})
        source = response.get("scriptSource", "")
        set_cached_script_source(script_id, source)
        return source
    except Exception as e:
        print(f"获取脚本源代码出错（{script_id}）：{e}")
        return ""


async def get_code_context(client, script_id, line_number, column_number):
    """
    获取当前断点位置前后各30个字符的代码片段：
    1. 先从缓存或CDP获取原始代码。
    2. 根据 line_number 与 column_number 计算当前断点在原始代码中的字符偏移量。
    3. 截取前后各30个字符的片段，对该片段进行格式化，再在断点位置插入标记。
    """
    try:
        raw_source = await get_script_source(client, script_id)
        if not raw_source:
            return {"context_lines": ["获取源代码失败"]}
        
        # 将原始代码按行拆分，计算偏移量
        lines = raw_source.splitlines()
        if line_number >= len(lines):
            # 如果行号超过文件总行数，则直接使用column_number
            offset = column_number
        else:
            # 计算前面所有行的字符数（每行加上换行符，假设换行符占1个字符）
            offset = sum(len(lines[i]) + 1 for i in range(line_number)) + column_number
        
        # 截取当前断点前后各30个字符的代码片段
        snippet_start = max(0, offset - 150)
        snippet_end = min(len(raw_source), offset + 150)
        snippet = raw_source[snippet_start:snippet_end]
        
        # 对该代码片段进行格式化
        formatted_snippet = jsbeautifier.beautify(snippet)
        
        # 计算断点在片段中的相对位置，并插入标记 "➤"
        marker_pos = offset - snippet_start
        snippet_with_marker = (
            formatted_snippet[:marker_pos] +
            "➤" +
            formatted_snippet[marker_pos:]
        )
        
        return {"context_lines": [snippet_with_marker]}
    except Exception as e:
        return {"context_lines": [f"获取源代码失败: {str(e)}"]}




async def get_script_url_by_id(client, script_id):
    """
    通过脚本源代码尝试获取 URL（此处直接返回脚本ID，扩展逻辑时可根据需要解析 URL）
    """
    source = await get_script_source(client, script_id)
    if not source:
        return f"脚本ID: {script_id}"
    return f"脚本ID: {script_id}"


async def get_call_stack(callFrames):
    """
    获取格式化的调用堆栈信息
    """
    call_stack = []
    for i, frame in enumerate(callFrames):
        function_name = frame.get("functionName") or "<匿名函数>"
        url = frame.get("url", "")
        line_number = frame["location"]["lineNumber"] + 1
        column_number = frame["location"].get("columnNumber", 0) + 1
        if url:
            script_location = f"{url}:{line_number}:{column_number}"
        else:
            script_id = frame["location"]["scriptId"]
            script_location = f"脚本ID:{script_id}, 行:{line_number}, 列:{column_number}"
        call_stack.append(f"{i+1}. {function_name} ({script_location})")
    return call_stack


async def get_object_properties(object_id, client, max_depth=2, current_depth=0, max_props=15, max_total_props=15):
    """
    获取对象属性信息，支持递归查询（限制递归深度和总属性数）
    
    优化点：
    - 减少递归深度和属性数量限制，降低内存占用
    - 对大型对象进行更严格的过滤
    - 添加内存使用监控和主动垃圾回收
    """
    # 初始化属性计数器（仅在顶层调用时）
    if current_depth == 0:
        get_object_properties.total_props_count = 0
        
    # 检查递归深度和属性数量限制
    if current_depth > max_depth or getattr(get_object_properties, 'total_props_count', 0) > max_total_props:
        return "[对象过大或嵌套过深]"
        
    try:
        # 获取对象属性
        props_resp = await client.send("Runtime.getProperties", {
            "objectId": object_id,
            "ownProperties": True,
            "accessorProperties": True,
            "generatePreview": True
        })
        
        all_props = props_resp.get("result", [])
        result_size = len(all_props)
        
        # 对大型对象进行更严格的过滤
        if result_size > 50 and current_depth > 0:
            return f"[大型对象: 包含约 {result_size} 个属性]"
            
        result = {}
        
        # 检测框架组件
        descriptions = [prop.get("value", {}).get("description", "") for prop in all_props if prop.get("value")]
        is_framework_component = any(("Vue" in desc or "_react" in desc or "React" in desc) for desc in descriptions)
        
        if is_framework_component and current_depth > 0:
            key_props = [p for p in all_props if p.get("name") in ["_data", "state", "props", "type", "id", "key"]]
            if key_props:
                for prop in key_props[:3]:  # 减少为最多3个关键属性
                    name = prop.get("name")
                    value_obj = prop.get("value")
                    if value_obj and "value" in value_obj:
                        result[name] = value_obj["value"]
                    else:
                        result[name] = value_obj.get("description", "[对象]") if value_obj else "[未知值]"
                return f"[框架组件: {', '.join(result.keys())}]"
            return "[框架组件]"
            
        # 分离重要属性和普通属性
        important_props = []
        normal_props = []
        important_names = ["id", "name", "key", "type", "value", "data", "url", "method", 
                         "token", "params", "response", "result", "error", "code", "status"]
        
        for prop in all_props:
            name = prop.get("name")
            if name in important_names:
                important_props.append(prop)
            else:
                normal_props.append(prop)
                
        # 选择要处理的属性
        selected_props = important_props + normal_props
        if len(selected_props) > max_props:
            selected_props = important_props + normal_props[:max_props - len(important_props)]
            result["_note"] = f"[属性过多，显示 {len(selected_props)}/{len(all_props)}]"
            
        # 处理选定的属性
        for prop in selected_props:
            name = prop.get("name")
            value_obj = prop.get("value")
            
            # 跳过不必要的属性
            if value_obj is None or should_skip_property(name, value_obj):
                continue
                
            get_object_properties.total_props_count += 1
            if get_object_properties.total_props_count > max_total_props:
                result["_truncated"] = "[达到最大属性限制]"
                break
                
            # 处理不同类型的属性值
            if "value" in value_obj:
                result[name] = value_obj["value"]
            elif "objectId" in value_obj and current_depth < max_depth:
                obj_type = value_obj.get("type")
                obj_subtype = value_obj.get("subtype")
                obj_class = value_obj.get("className", "")
                obj_desc = value_obj.get("description", "")
                
                # 处理数组
                if obj_type == "object" and obj_subtype == "array":
                    if "preview" in value_obj:
                        preview = value_obj["preview"]
                        properties = preview.get("properties", [])
                        if len(properties) <= 3:  # 减少为最多3个元素
                            array_values = []
                            for item in properties:
                                if "value" in item:
                                    array_values.append(item["value"])
                                else:
                                    array_values.append(item.get("description", "[对象]"))
                            result[name] = array_values
                        else:
                            length = len(properties)
                            result[name] = f"[数组: {length}个元素]"
                    else:
                        result[name] = obj_desc
                # 处理重要对象类型
                elif name in ["params", "data"] or (
                     current_depth == 0 and obj_type == "object" and not obj_subtype):
                    nested_props = await get_object_properties(
                        value_obj["objectId"], 
                        client, 
                        max_depth, 
                        current_depth + 1,
                        max_props,
                        max_total_props
                    )
                    result[name] = nested_props
                # 处理HTML元素
                elif "HTML" in obj_class or "Element" in obj_class:
                    result[name] = f"[{obj_desc}]"
                else:
                    result[name] = obj_desc
            else:
                result[name] = value_obj.get("description", "[未知值]")
                
        # 主动触发垃圾回收（仅在顶层调用时）
        if current_depth == 0 and result_size > 50:
            gc.collect()
            
        return result
    except Exception as e:
        return {"错误": str(e)}


async def process_debugger_paused(event, client):
    """
    处理调试器暂停事件，收集断点信息、代码上下文、调用堆栈以及作用域变量
    
    优化点：
    - 减少收集的调试信息量，降低内存占用
    - 实现增量数据收集，避免一次性加载大量数据
    - 添加内存使用监控和主动垃圾回收
    - 对大型调用堆栈和作用域进行更严格的过滤
    """
    # 检查内存使用情况
    memory_info = memory_manager.get_memory_info()
    high_memory_usage = memory_info['percent'] > 70
    
    divider = "=" * 60
    debug_info = f"\n{divider}\n🔍 调试器已暂停\n{divider}\n"
    callFrames = event.get("callFrames", [])
    
    if not callFrames:
        debug_info += "⚠️ 无法获取调用帧信息\n"
        print(debug_info)
        return debug_info

    # 获取顶层调用帧信息
    top_frame = callFrames[0]
    script_id = top_frame["location"]["scriptId"]
    line_number = top_frame["location"]["lineNumber"]
    col_number = top_frame["location"].get("columnNumber", 0)
    function_name = top_frame.get("functionName") or "<匿名函数>"
    
    # 内存优化：在高内存使用情况下减少收集的信息
    max_call_frames = 3 if high_memory_usage else 5
    max_scope_frames = 1 if high_memory_usage else 2
    
    # 顺序获取信息而不是并行，以减少峰值内存使用
    script_url = await get_script_url_by_id(client, script_id)
    debug_info += f"📍 暂停位置: {function_name} 在 {script_url}\n"
    debug_info += f"📍 具体位置: 行 {line_number+1}, 列 {col_number+1}\n\n"
    
    # 获取代码上下文
    code_context = await get_code_context(client, script_id, line_number, col_number)
    debug_info += "📝 代码上下文:\n"
    for line in code_context.get("context_lines", []):
        debug_info += f"{line}\n"
    debug_info += "\n"
    
    # 获取调用堆栈（限制数量）
    call_stack = await get_call_stack(callFrames[:max_call_frames])
    if call_stack:
        debug_info += "🔄 调用堆栈:\n"
        for frame_info in call_stack:
            debug_info += f"  {frame_info}\n"
        debug_info += "\n"
    
    # 主动触发垃圾回收，释放前面步骤的临时对象
    gc.collect()
    
    # 收集作用域变量
    debug_info += "🔍 作用域变量:\n"
    found_interesting_scope = False
    
    # 使用分批处理而不是并行任务
    for i, frame in enumerate(callFrames[:max_scope_frames]):
        if high_memory_usage and i > 0:
            break  # 高内存使用时只处理顶层帧
            
        frame_name = frame.get("functionName") or f"<匿名函数 {i}>"
        relevant_scopes = []
        
        # 过滤出相关的作用域
        for scope in frame.get("scopeChain", []):
            scope_type = scope.get("type")
            if scope_type not in ("local", "block") or scope_type == "this":
                continue
                
            obj_desc = scope.get("object", {}).get("description", "")
            if obj_desc in ("Window", "options"):
                continue
                
            object_id = scope.get("object", {}).get("objectId")
            if not object_id:
                continue
                
            relevant_scopes.append({
                "object_id": object_id,
                "scope_type": scope_type,
                "frame_name": frame_name
            })
        
        # 限制每个帧处理的作用域数量
        max_scopes = 1 if high_memory_usage else 2
        for scope_info in relevant_scopes[:max_scopes]:
            # 获取作用域属性
            scope_properties = await get_object_properties(
                scope_info["object_id"], 
                client,
                max_depth=1 if high_memory_usage else 2
            )
            
            if not scope_properties:
                continue
                
            found_interesting_scope = True
            scope_type_cn = {"local": "局部", "block": "块级"}.get(scope_info["scope_type"], scope_info["scope_type"])
            debug_info += f"  📋 {scope_type_cn}作用域 ({scope_info['frame_name']}):\n"
            
            # 限制输出的属性数量
            max_props_to_show = 10 if high_memory_usage else 20
            prop_count = 0
            
            for name, value in scope_properties.items():
                prop_count += 1
                if prop_count > max_props_to_show:
                    debug_info += f"    ... 还有 {len(scope_properties) - max_props_to_show} 个属性未显示 ...\n"
                    break
                debug_info += f"    {name}: {json.dumps(value, ensure_ascii=False)}\n"
            
            # 每处理完一个作用域就主动触发垃圾回收
            gc.collect()
    
    if not found_interesting_scope:
        debug_info += "  [作用域中未找到相关变量]\n"
    
    debug_info += f"\n{divider}\n"
    print(debug_info)
    
    # 返回前再次触发垃圾回收
    gc.collect()
    return debug_info
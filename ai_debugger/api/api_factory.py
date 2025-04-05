# API工厂模块
# 用于根据模型类型创建相应的API实例

class APIFactory:
    """API工厂类，用于创建不同类型的API实例"""
    
    @staticmethod
    def create_api(model_type="qwen"):
        """根据模型类型创建API实例
        
        Args:
            model_type: 模型类型，可选值为"qwen"、"gpt"、"deepseek"、"ernie"或"spark"，默认为"qwen"
            
        Returns:
            object: API实例，包含get_debug_instruction和debugger_analyze方法
        """
        if model_type == "gpt":
            from ai_debugger.api.gpt_api import get_debug_instruction, debugger_analyze
        elif model_type == "deepseek":
            from ai_debugger.api.deepseek_api import get_debug_instruction, debugger_analyze
        elif model_type == "ernie":
            from ai_debugger.api.ernie_api import get_debug_instruction, debugger_analyze
        elif model_type == "spark":
            from ai_debugger.api.spark_api import get_debug_instruction, debugger_analyze
        else:  # 默认使用通义千问
            from ai_debugger.api.qwen_api import get_debug_instruction, debugger_analyze
            
        # 创建一个简单的对象，包含所需的方法
        class APIWrapper:
            @staticmethod
            def get_debug_instruction(step_output):
                return get_debug_instruction(step_output)
                
            @staticmethod
            def debugger_analyze(path):
                return debugger_analyze(path)
                
        return APIWrapper()

# 导出工厂函数，保持与原始get_api_module函数兼容
def get_api_module(model_type="qwen"):
    """根据模型类型返回相应的API模块
    
    Args:
        model_type: 模型类型，可选值为"qwen"、"gpt"、"deepseek"、"ernie"或"spark"，默认为"qwen"
        
    Returns:
        object: 包含get_debug_instruction和debugger_analyze方法的对象
    """
    return APIFactory.create_api(model_type)
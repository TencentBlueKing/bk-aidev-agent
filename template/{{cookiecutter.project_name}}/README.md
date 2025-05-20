# Quickstart

## 1. 本地快速启动

## 1.1 配置环境

执行下面的脚本,创建虚拟环境&安装依赖

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

根据实际情况配置外部依赖的环境变量`.env`,可以使用下面这个脚本将`app_desc.yml`的变量到处到`.env`文件

```python
#!/usr/bin/env python3
import yaml

def extract_env_variables(yaml_file):
    """
    Extract key-value pairs from env_variables in a YAML file.
    
    Args:
        yaml_file (str): Path to the YAML file
        
    Returns:
        dict: Dictionary containing key-value pairs from env_variables
    """
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    env_vars = {}
    if 'modules' in data and 'default' in data['modules']:
        module = data['modules']['default']
        if 'env_variables' in module:
            for var in module['env_variables']:
                env_vars[var['key']] = var['value']
    
    return env_vars

if __name__ == "__main__":
    # Example usage:
    yaml_file = "app_desc.yml"  # Update this path as needed
    env_vars = extract_env_variables(yaml_file)
    
    export to .env file
    with open(".env", "w") as fo:
        for key, value in env_vars.items():
            fo.write(f"export {key}={value}\n")
```

## 1.2 启动服务并测试

执行下面脚本本地启动服务

```bash
source .env
python bin/manage.py migrate
python bin/manage.py runserver 0.0.0.0:5000
```
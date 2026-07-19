"""
Qlib 数据下载脚本
用法:
    python scripts/get_data.py --target_dir ~/.qlib/qlib_data/cn_data --region cn
    python scripts/get_data.py --target_dir ~/.qlib/qlib_data/us_data --region us
"""

import fire
import qlib
from qlib.config import REG_CN, REG_US
import urllib.request
import tarfile
import os
import sys


def download_data(target_dir: str, region: str = "cn"):
    """下载 Qlib 预处理的二进制数据"""
    
    if region == "cn":
        url = "https://qlib-data.quantilians.com/qlib_data_cn.zip"
        reg = REG_CN
    elif region == "us":
        url = "https://qlib-data.quantilians.com/qlib_data_us.zip"
        reg = REG_US
    else:
        print(f"不支持的区域: {region}，请使用 'cn' 或 'us'")
        sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)
    
    # 检查是否已存在
    if os.path.exists(os.path.join(target_dir, "features")):
        print(f"数据已存在于 {target_dir}，跳过下载")
        return

    zip_path = os.path.join(target_dir, "..", "qlib_data.zip")
    zip_path = os.path.abspath(zip_path)

    print(f"正在从 {url} 下载数据...")
    print(f"目标路径: {target_dir}")
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("下载完成，正在解压...")
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(os.path.dirname(target_dir))
        
        os.remove(zip_path)
        print(f"✅ 数据准备完成: {target_dir}")
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print("")
        print("手动下载方式:")
        print(f"  1. 访问: {url}")
        print(f"  2. 解压到: {target_dir}")
        sys.exit(1)

    # 验证
    try:
        qlib.init(provider_uri=target_dir, region=reg)
        from qlib.data import D
        df = D.features(['SH600000'], ['close'], 
                       start_time='2020-01-01', end_time='2020-01-10')
        print(f"✅ 数据验证通过，共 {len(df)} 条记录")
    except Exception as e:
        print(f"⚠️ 数据验证失败: {e}")


if __name__ == "__main__":
    fire.Fire(download_data)

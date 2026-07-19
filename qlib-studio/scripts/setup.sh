#!/bin/bash
# Qlib Studio 快速启动脚本
set -e

echo "=========================================="
echo "  Qlib Studio - 快速启动脚本"
echo "=========================================="

# 1. 检查 Python 版本
echo ""
echo "[1/5] 检查 Python 环境..."
python3 --version || { echo "Python3 未安装！"; exit 1; }

# 2. 安装后端依赖
echo ""
echo "[2/5] 安装后端依赖..."
cd backend
pip install -r requirements.txt || { echo "依赖安装失败！"; exit 1; }
cd ..

# 3. 下载 Qlib 数据
echo ""
echo "[3/5] 检查 Qlib 数据..."
if [ ! -d "$HOME/.qlib/qlib_data/cn_data" ]; then
    echo "数据不存在，开始下载..."
    python3 -c "
import qlib
from qlib.constant import REG_CN
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data', region=REG_CN)
from qlib.data import D
D.features(['SH600000'], ['close'], start_time='2020-01-01', end_time='2020-01-10')
print('Data check passed')
" 2>/dev/null || {
        echo "首次使用，请手动下载数据："
        echo "  python3 scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn"
    }
else
    echo "数据已存在，跳过下载"
fi

# 4. 安装前端依赖
echo ""
echo "[4/5] 安装前端依赖..."
cd frontend
npm install || { echo "前端依赖安装失败！"; exit 1; }
cd ..

# 5. 启动服务
echo ""
echo "[5/5] 启动服务..."
echo ""
echo "=========================================="
echo "  启动方式："
echo "  1. Docker 一键启动: docker-compose -f docker/docker-compose.yml up -d"
echo "  2. 手动启动后端:    cd backend && uvicorn main:app --reload"
echo "  3. 手动启动前端:    cd frontend && npm run dev"
echo ""
echo "  前端访问: http://localhost:3000"
echo "  后端API: http://localhost:8000/docs"
echo "=========================================="

# 询问是否立即启动
read -p "是否立即启动后端服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启动后端服务..."
    cd backend
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    echo "后端已启动: http://localhost:8000"
    echo "API 文档: http://localhost:8000/docs"
    cd ..
    
    read -p "是否同时启动前端？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd frontend
        npm run dev &
        echo "前端已启动: http://localhost:3000"
        cd ..
    fi
fi

echo ""
echo "🎉 Qlib Studio 启动完成！"

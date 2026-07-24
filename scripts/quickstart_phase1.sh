#!/bin/bash
# ============================================================
# Qlib Studio Phase 1 快速启动脚本
# 功能：Rolling 训练 + 每日预测 + 定时任务
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
CONFIG_DIR="$SCRIPT_DIR/configs"

# 切换到项目目录
cd "$SCRIPT_DIR"

print_header "Qlib Studio Phase 1 快速启动"

# ============================================================
# Step 1: 检查依赖
# ============================================================
print_info "Step 1: 检查依赖..."

check_python() {
    if ! command -v python &> /dev/null; then
        print_error "Python 未安装，请先安装 Python 3.8+"
        exit 1
    fi
    print_info "Python 版本：$(python --version)"
}

check_packages() {
    local missing=()
    
    for package in pyqlib APScheduler pandas numpy; do
        if ! python -c "import $package" 2>/dev/null; then
            missing+=($package)
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        print_warning "缺少以下依赖包：${missing[*]}"
        read -p "是否现在安装？(y/n): " install
        if [ "$install" = "y" ]; then
            print_info "安装依赖中..."
            cd "$BACKEND_DIR"
            pip install -r requirements.txt
            cd "$SCRIPT_DIR"
        else
            print_warning "跳过依赖安装，后续请手动运行：pip install -r backend/requirements.txt"
        fi
    else
        print_info "所有依赖已安装"
    fi
}

check_python
check_packages

# ============================================================
# Step 2: 创建必要目录
# ============================================================
print_info "Step 2: 创建必要目录..."

mkdir -p "$BACKEND_DIR/experiments"
mkdir -p "$BACKEND_DIR/predictions"
mkdir -p "$BACKEND_DIR/logs"

print_info "目录创建完成"

# ============================================================
# Step 3: 准备配置文件
# ============================================================
print_info "Step 3: 准备配置文件..."

if [ ! -f "$CONFIG_DIR/my_strategy.yaml" ]; then
    cp "$CONFIG_DIR/example_full.yaml" "$CONFIG_DIR/my_strategy.yaml"
    print_info "已复制示例配置到 configs/my_strategy.yaml"
    print_warning "请根据需要编辑 configs/my_strategy.yaml 调整参数"
else
    print_info "配置文件已存在：configs/my_strategy.yaml"
fi

if [ ! -f "$CONFIG_DIR/scheduler_config_custom.yaml" ]; then
    cp "$CONFIG_DIR/scheduler_config.yaml" "$CONFIG_DIR/scheduler_config_custom.yaml"
    print_info "已复制调度器配置到 configs/scheduler_config_custom.yaml"
fi

# ============================================================
# Step 4: 选择启动模式
# ============================================================
print_header "选择启动模式"

echo "1. Rolling 训练（历史回测）"
echo "2. 单次预测（手动执行）"
echo "3. 定时任务调度器（自动运行）"
echo "4. 查看帮助文档"
echo "5. 退出"
echo ""

read -p "请选择 (1-5): " choice

case $choice in
    1)
        print_header "Rolling 训练"
        
        # 设置训练参数
        read -p "训练窗口大小（默认 630 天）: " window_size
        window_size=${window_size:-630}
        
        read -p "滚动步长（默认 252 天）: " step_size
        step_size=${step_size:-252}
        
        read -p "开始日期（默认 2018-01-01）: " start_date
        start_date=${start_date:-"2018-01-01"}
        
        read -p "结束日期（默认 2024-12-31）: " end_date
        end_date=${end_date:-"2024-12-31"}
        
        read -p "模式（rolling/expanding，默认 rolling）: " mode
        mode=${mode:-"rolling"}
        
        print_info "开始 Rolling 训练..."
        print_info "参数：窗口=$window_size, 步长=$step_size, 模式=$mode"
        print_info "时间范围：$start_date ~ $end_date"
        
        cd "$BACKEND_DIR"
        python rolling_trainer.py \
            --experiment-dir ./experiments \
            --window-size $window_size \
            --step-size $step_size \
            --mode $mode \
            --calendar-start $start_date \
            --calendar-end $end_date \
            --config ../configs/my_strategy.yaml \
            --force
        
        print_header "训练完成！"
        print_info "查看结果："
        print_info "  - 模型文件：ls -la experiments/rolling_experiments/"
        print_info "  - 训练历史：cat experiments/rolling_experiments/history.json"
        ;;
        
    2)
        print_header "单次预测"
        
        read -p "股票池（csi300/csi500/all，默认 csi300）: " universe
        universe=${universe:-"csi300"}
        
        read -p "持仓数量（默认 50）: " top_k
        top_k=${top_k:-50}
        
        read -p "调出数量（默认 5）: " n_drop
        n_drop=${n_drop:-5}
        
        read -p "数据源（akshare/tushare/qlib，默认 akshare）: " provider
        provider=${provider:-"akshare"}
        
        print_info "开始预测..."
        
        cd "$BACKEND_DIR"
        python daily_prediction.py \
            --model-dir ./experiments \
            --universe $universe \
            --top-k $top_k \
            --n-drop $n_drop \
            --output-dir ./predictions \
            --provider $provider
        
        print_header "预测完成！"
        print_info "查看结果："
        print_info "  - 信号文件：ls -la predictions/signals_*.json"
        print_info "  - 完整结果：cat predictions/pipeline_result_*.json"
        ;;
        
    3)
        print_header "定时任务调度器"
        
        echo "1. 前台运行（实时查看日志）"
        echo "2. 后台运行（nohup）"
        echo "3. 查看任务状态"
        echo "4. 手动触发任务"
        echo ""
        
        read -p "请选择 (1-4): " scheduler_choice
        
        case $scheduler_choice in
            1)
                print_info "启动调度器（前台模式）..."
                cd "$BACKEND_DIR"
                python task_scheduler.py \
                    --config ../configs/scheduler_config_custom.yaml \
                    --experiment-dir ./experiments \
                    --model-dir ./experiments \
                    --output-dir ./predictions \
                    --action start
                ;;
                
            2)
                print_info "启动调度器（后台模式）..."
                cd "$BACKEND_DIR"
                nohup python task_scheduler.py \
                    --config ../configs/scheduler_config_custom.yaml \
                    --experiment-dir ./experiments \
                    --model-dir ./experiments \
                    --output-dir ./predictions \
                    --action start > logs/scheduler.log 2>&1 &
                
                SCHEDULER_PID=$!
                print_info "调度器已启动，PID: $SCHEDULER_PID"
                print_info "查看日志：tail -f logs/scheduler.log"
                print_info "停止调度器：kill $SCHEDULER_PID"
                ;;
                
            3)
                print_info "查看任务状态..."
                cd "$BACKEND_DIR"
                python task_scheduler.py \
                    --config ../configs/scheduler_config_custom.yaml \
                    --action status
                ;;
                
            4)
                echo "1. rolling_train（滚动训练）"
                echo "2. daily_predict（每日预测）"
                echo "3. data_update（数据更新）"
                echo ""
                
                read -p "选择要触发的任务 (1-3): " task_choice
                
                case $task_choice in
                    1) task_name="rolling_train" ;;
                    2) task_name="daily_predict" ;;
                    3) task_name="data_update" ;;
                    *) print_error "无效选择"; exit 1 ;;
                esac
                
                print_info "手动触发任务：$task_name"
                cd "$BACKEND_DIR"
                python task_scheduler.py \
                    --config ../configs/scheduler_config_custom.yaml \
                    --action run \
                    --task $task_name
                ;;
                
            *)
                print_error "无效选择"
                exit 1
                ;;
        esac
        ;;
        
    4)
        print_header "帮助文档"
        echo "详细文档位置：docs/PHASE1_IMPLEMENTATION.md"
        echo ""
        echo "快速参考："
        echo ""
        echo "# Rolling 训练"
        echo "python backend/rolling_trainer.py --help"
        echo ""
        echo "# 每日预测"
        echo "python backend/daily_prediction.py --help"
        echo ""
        echo "# 任务调度"
        echo "python backend/task_scheduler.py --help"
        echo ""
        echo "# 查看配置示例"
        echo "cat configs/scheduler_config.yaml"
        ;;
        
    5)
        print_info "退出"
        exit 0
        ;;
        
    *)
        print_error "无效选择"
        exit 1
        ;;
esac

print_header "操作完成"
print_info "如有问题，请查看文档：docs/PHASE1_IMPLEMENTATION.md"

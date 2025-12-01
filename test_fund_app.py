import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="基金组合分析工具", page_icon="📊", layout="wide")

st.title("📊 基金组合分析工具")

# ============ 侧边栏：参数设置 ============
st.sidebar.header("⚙️ 参数设置")

# 模拟基金数据
@st.cache_data
def generate_fund_data(funds, days=252):
    """生成模拟的基金净值数据"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.today(), periods=days, freq='D')
    
    data = {'日期': dates}
    for fund, params in funds.items():
        # 使用几何布朗运动模拟净值
        returns = np.random.normal(params['mean'], params['volatility'], days)
        prices = [1.0]
        for r in returns[1:]:
            prices.append(prices[-1] * (1 + r))
        data[fund] = prices
    
    return pd.DataFrame(data)

# 定义基金池
fund_pool = {
    '沪深300指数A': {'mean': 0.0003, 'volatility': 0.015},
    '中证500指数A': {'mean': 0.0004, 'volatility': 0.018},
    '创业板指数A': {'mean': 0.0005, 'volatility': 0.022},
    '债券型基金A': {'mean': 0.0001, 'volatility': 0.003},
    '货币基金A': {'mean': 0.00008, 'volatility': 0.0005},
    '黄金ETF': {'mean': 0.0002, 'volatility': 0.012},
    '纳斯达克指数': {'mean': 0.0004, 'volatility': 0.016},
}

# 选择基金
selected_funds = st.sidebar.multiselect(
    "选择基金（可多选）",
    options=list(fund_pool.keys()),
    default=['沪深300指数A', '债券型基金A', '货币基金A']
)

# 时间范围
days = st.sidebar.slider("回测天数", 30, 500, 252)

# 无风险利率
risk_free_rate = st.sidebar.number_input("无风险年化利率 (%)", 0.0, 10.0, 2.5, 0.1) / 100

if not selected_funds:
    st.warning("请至少选择一只基金")
    st.stop()

# 生成数据
selected_pool = {k: v for k, v in fund_pool.items() if k in selected_funds}
df = generate_fund_data(selected_pool, days)

# ============ 组合权重设置 ============
st.sidebar.subheader("📊 组合权重配置")
weights = {}
remaining = 100

for i, fund in enumerate(selected_funds):
    if i == len(selected_funds) - 1:
        weights[fund] = remaining
        st.sidebar.text(f"{fund}: {remaining}%")
    else:
        w = st.sidebar.slider(f"{fund} (%)", 0, remaining, min(remaining, 100 // len(selected_funds)))
        weights[fund] = w
        remaining -= w

weights = {k: v/100 for k, v in weights.items()}

# ============ 核心计算函数 ============
def calculate_metrics(prices: pd.Series, risk_free: float = 0.025):
    """计算各项风险收益指标"""
    returns = prices.pct_change().dropna()
    
    # 年化收益率
    total_return = (prices.iloc[-1] / prices.iloc[0]) - 1
    annual_return = (1 + total_return) ** (252 / len(prices)) - 1
    
    # 年化波动率
    annual_volatility = returns.std() * np.sqrt(252)
    
    # 夏普比率
    sharpe = (annual_return - risk_free) / annual_volatility if annual_volatility > 0 else 0
    
    # 最大回撤
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    max_drawdown = drawdown.min()
    
    # 卡玛比率
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    # 胜率
    win_rate = (returns > 0).sum() / len(returns)
    
    return {
        '累计收益率': f"{total_return:.2%}",
        '年化收益率': f"{annual_return:.2%}",
        '年化波动率': f"{annual_volatility:.2%}",
        '夏普比率': f"{sharpe:.2f}",
        '最大回撤': f"{max_drawdown:.2%}",
        '卡玛比率': f"{calmar:.2f}",
        '日胜率': f"{win_rate:.2%}",
    }

def calculate_portfolio(df, weights):
    """计算组合净值"""
    portfolio = pd.Series(0.0, index=df.index)
    for fund, weight in weights.items():
        portfolio += df[fund] * weight
    return portfolio

# ============ 主面板 ============
tab1, tab2, tab3, tab4 = st.tabs(["📈 净值走势", "📊 指标分析", "🔥 相关性分析", "📉 回撤分析"])

with tab1:
    st.subheader("净值走势对比")
    
    # 计算组合净值
    df['投资组合'] = calculate_portfolio(df, weights)
    
    # 归一化处理
    df_normalized = df.copy()
    for col in df_normalized.columns:
        if col != '日期':
            df_normalized[col] = df_normalized[col] / df_normalized[col].iloc[0]
    
    # 绘制走势图
    fig = px.line(
        df_normalized.melt(id_vars='日期', var_name='基金', value_name='净值'),
        x='日期', y='净值', color='基金',
        title='归一化净值走势（起点=1）'
    )
    fig.update_layout(hovermode='x unified', height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # 显示原始数据
    with st.expander("查看原始数据"):
        st.dataframe(df.tail(20), use_container_width=True)

with tab2:
    st.subheader("风险收益指标")
    
    # 计算各基金指标
    metrics_data = []
    for fund in selected_funds + ['投资组合']:
        metrics = calculate_metrics(df[fund], risk_free_rate)
        metrics['基金名称'] = fund
        metrics_data.append(metrics)
    
    metrics_df = pd.DataFrame(metrics_data)
    cols = ['基金名称'] + [c for c in metrics_df.columns if c != '基金名称']
    metrics_df = metrics_df[cols]
    
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
    
    # 风险收益散点图
    st.subheader("风险收益散点图")
    scatter_data = []
    for fund in selected_funds + ['投资组合']:
        returns = df[fund].pct_change().dropna()
        total_return = (df[fund].iloc[-1] / df[fund].iloc[0]) - 1
        annual_return = (1 + total_return) ** (252 / len(df)) - 1
        annual_vol = returns.std() * np.sqrt(252)
        scatter_data.append({
            '基金': fund,
            '年化收益率': annual_return,
            '年化波动率': annual_vol
        })
    
    scatter_df = pd.DataFrame(scatter_data)
    fig2 = px.scatter(
        scatter_df, x='年化波动率', y='年化收益率', 
        text='基金', size_max=60,
        title='风险收益分布（右上角最优）'
    )
    fig2.update_traces(textposition='top center', marker=dict(size=15))
    fig2.update_layout(height=500)
    st.plotly_chart(fig2, use_container_width=True)

with tab3:
    st.subheader("基金相关性矩阵")
    
    # 计算日收益率
    returns_df = df[selected_funds].pct_change().dropna()
    corr_matrix = returns_df.corr()
    
    # 热力图
    fig3 = px.imshow(
        corr_matrix,
        text_auto='.2f',
        color_continuous_scale='RdBu_r',
        aspect='auto',
        title='日收益率相关性矩阵'
    )
    fig3.update_layout(height=500)
    st.plotly_chart(fig3, use_container_width=True)
    
    st.info("💡 相关性越低，组合分散风险效果越好。负相关的资产可以有效对冲风险。")

with tab4:
    st.subheader("回撤分析")
    
    # 计算回撤
    drawdown_df = pd.DataFrame({'日期': df['日期']})
    for fund in selected_funds + ['投资组合']:
        cummax = df[fund].cummax()
        drawdown_df[fund] = (df[fund] - cummax) / cummax
    
    # 绘制回撤图
    fig4 = px.area(
        drawdown_df.melt(id_vars='日期', var_name='基金', value_name='回撤'),
        x='日期', y='回撤', color='基金',
        title='历史回撤走势'
    )
    fig4.update_layout(hovermode='x unified', height=500)
    fig4.update_yaxes(tickformat='.1%')
    st.plotly_chart(fig4, use_container_width=True)
    
    # 最大回撤统计
    st.subheader("最大回撤排名")
    max_dd = {fund: drawdown_df[fund].min() for fund in selected_funds + ['投资组合']}
    max_dd_df = pd.DataFrame([
        {'基金': k, '最大回撤': v} for k, v in sorted(max_dd.items(), key=lambda x: x[1], reverse=True)
    ])
    
    fig5 = px.bar(max_dd_df, x='基金', y='最大回撤', title='最大回撤对比')
    fig5.update_yaxes(tickformat='.1%')
    fig5.update_traces(marker_color=['green' if x > -0.1 else 'orange' if x > -0.2 else 'red' for x in max_dd_df['最大回撤']])
    st.plotly_chart(fig5, use_container_width=True)

# ============ 底部信息 ============
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("组合基金数量", len(selected_funds))
with col2:
    portfolio_return = (df['投资组合'].iloc[-1] / df['投资组合'].iloc[0]) - 1
    st.metric("组合累计收益", f"{portfolio_return:.2%}")
with col3:
    portfolio_dd = ((df['投资组合'] - df['投资组合'].cummax()) / df['投资组合'].cummax()).min()
    st.metric("组合最大回撤", f"{portfolio_dd:.2%}")

st.caption("⚠️ 本工具仅供学习演示，数据为模拟生成，不构成投资建议。")

import streamlit as st
import pandas as pd
import numpy as np
import io
from openpyxl import Workbook

# --- 配置部分 ---
# 番数规则定义
RULES = {
    1: 16, 2: 8, 3: 8, 4: 8, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4,
    10: 2, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2, 16: 2, 17: 2, 18: 1, 19: 2
}

def calculate_hupai_details(hupai_val):
    """
    处理胡牌字段，计算总胡牌番数、自摸番数、除去自摸番数
    """
    try:
        val_str = str(int(float(hupai_val)))
        if val_str == '0':
            return 0, 0, 0
        
        # 填充为9位并拆分
        val_str = val_str.zfill(9)
        parts = [val_str[0], val_str[1:3], val_str[3:5], val_str[5:7], val_str[7:9]]
        
        total_product = 1
        zimo_product = 1
        no_zimo_product = 1
        
        found_any = False
        found_zimo = False
        found_no_zimo = False
        
        for p in parts:
            num = int(p)
            if num in RULES:
                total_product *= RULES[num]
                found_any = True
                if num == 17: # 17代表自摸
                    zimo_product *= RULES[num]
                    found_zimo = True
                else: # 非自摸
                    no_zimo_product *= RULES[num]
                    found_no_zimo = True
        
        res_total = total_product if found_any else 0
        res_zimo = zimo_product if found_zimo else 0
        res_no_zimo = no_zimo_product if found_no_zimo else 0
        
        return res_total, res_zimo, res_no_zimo
    except:
        return 0, 0, 0

def process_data(uploaded_file):
    try:
        # 读取原始数据，尝试 GBK 和 UTF-8 编码
        try:
            df = pd.read_csv(uploaded_file, encoding='gbk')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        
        # 清洗列名空格
        df.columns = [c.strip() for c in df.columns]

        # 计算新增列
        results = df['胡牌'].apply(calculate_hupai_details)
        df['总胡牌番数'] = [x[0] for x in results]
        df['自摸'] = [x[1] for x in results]
        df['除去自摸胡牌番数'] = [x[2] for x in results]

        # 1. 亮倒相关统计
        ld_total = df[df['亮倒'] == 1].groupby('房间ID')['对局唯一识别号'].nunique()
        no_ld_df = df[df['亮倒'] == 0]
        no_ld_game_counts = no_ld_df.groupby(['房间ID', '对局唯一识别号']).size()
        no_ld_count = no_ld_game_counts[no_ld_game_counts == 3].reset_index().groupby('房间ID').size()
        ld_win = df[(df['亮倒'] == 1) & (df['胡牌'] != 0)].groupby('房间ID')['对局唯一识别号'].nunique()
        ld_win_rate = (ld_win / ld_total * 100).fillna(0)

        ld_stats = pd.DataFrame({
            '亮倒局数': ld_total,
            '不亮局数(3人局)': no_ld_count,
            '亮倒胡牌局数': ld_win,
            '亮倒胡牌率(%)': ld_win_rate
        }).reset_index().fillna(0)

        # 2. 买马统计
        buy_horse_df = df[(df['买马'] != 0) & (df['类型'] != '机器人')]
        buy_horse_pivot = buy_horse_df.pivot_table(index='房间ID', columns='买马', values='对局唯一识别号', aggfunc='nunique').fillna(0)

        no_buy_df = df[(df['买马'] == 0) & (df['类型'] != '机器人')]
        no_buy_game_counts = no_buy_df.groupby(['房间ID', '对局唯一识别号']).size()
        no_buy_count = no_buy_game_counts[no_buy_game_counts == 3].reset_index().groupby('房间ID').size()
        no_buy_stats = no_buy_count.reset_index().rename(columns={0: '不买马(3人局)局数'})

        # 3. 漂分统计
        piaofen_pivot = df.pivot_table(index='漂分', columns='房间ID', values='玩家ID', aggfunc='count').fillna(0)

        # 4. 胡牌番型统计
        zimo_pivot = df[df['总胡牌番数'] > 0].pivot_table(index='房间ID', columns='总胡牌番数', values='对局唯一识别号', aggfunc='nunique').fillna(0)
        no_zimo_pivot = df[df['除去自摸胡牌番数'] > 0].pivot_table(index='房间ID', columns='除去自摸胡牌番数', values='对局唯一识别号', aggfunc='nunique').fillna(0)

        # 导出到内存中的 Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ld_stats.to_excel(writer, sheet_name='亮倒统计', index=False)
            buy_horse_pivot.to_excel(writer, sheet_name='买马统计-买马')
            no_buy_stats.to_excel(writer, sheet_name='买马统计-不买马', index=False)
            piaofen_pivot.to_excel(writer, sheet_name='漂分统计')
            zimo_pivot.to_excel(writer, sheet_name='胡牌番型-自摸')
            no_zimo_pivot.to_excel(writer, sheet_name='胡牌番型-除去自摸')
        
        output.seek(0)
        return output, df

    except Exception as e:
        st.error(f"处理文件时出错: {str(e)}")
        return None, None

# --- UI 部分 ---
st.set_page_config(page_title="卡五星房间数值-游戏行为", layout="wide")

st.title("📊 卡五星房间数值-游戏行为")
st.markdown("---")

# 侧边栏：计算说明
with st.sidebar:
    st.header("📖 计算说明")
    st.markdown("""
    ### 1. 胡牌番数计算
    - **胡牌字段解析**：将9位数字拆分为5个部分（1位+2位*4）。
    - **番数规则**：根据预设的 `RULES` 字典将每个部分映射为对应番数并累乘。
    - **自摸识别**：规则 ID 为 17 的部分识别为自摸番数。

    ### 2. 亮倒统计
    - **亮倒局数**：统计亮倒字段为 1 的唯一对局数。
    - **不亮局数**：统计亮倒字段为 0 且参与人数为 3 人的唯一对局数。
    - **亮倒胡牌率**：亮倒且胡牌的局数 / 总亮倒局数。

    ### 3. 买马统计
    - 排除机器人玩家，统计不同买马倍数的局数，以及不买马（3人局）的局数。

    ### 4. 漂分统计
    - 统计各房间在不同漂分值下的玩家分布。

    ### 5. 番型统计
    - 分别统计自摸和非自摸情况下的番数分布局数。
    """)

# 主界面：文件上传
uploaded_file = st.file_uploader("选择 PlayRecord***.log 文件", type=['log', 'csv', 'txt'])

if uploaded_file is not None:
    st.info(f"已上传文件: {uploaded_file.name}")
    
    with st.spinner("正在处理数据，请稍候..."):
        excel_data, cleaned_df = process_data(uploaded_file)
        
        if excel_data:
            st.success("✅ 数据处理成功！")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 下载分析报表 (Excel)",
                    data=excel_data,
                    file_name="Game_Analysis_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                # 同时也提供清洗后的 CSV 下载
                csv_buffer = io.StringIO()
                cleaned_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下载清洗后的源数据 (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name="Game_Data_Cleaned.csv",
                    mime="text/csv"
                )

            # 预览数据
            st.subheader("📋 数据预览 (前5行)")
            st.dataframe(cleaned_df.head())
            
            # 展示一些基础统计图表（可选）
            st.subheader("📈 快速统计预览")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("总记录数", len(cleaned_df))
            with c2:
                st.metric("房间数", cleaned_df['房间ID'].nunique())
            with c3:
                st.metric("唯一对局数", cleaned_df['对局唯一识别号'].nunique())
else:
    st.warning("请上传日志文件以开始分析。")

# 页脚
st.markdown("---")
st.caption("© 2026 卡五星游戏数据分析工具 - 由 Trae 助手生成")

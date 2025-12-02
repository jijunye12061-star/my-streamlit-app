"""
轻量级需求管理系统
基于 Streamlit + SQLite

运行方式：
1. pip install streamlit
2. streamlit run app.py
"""

import streamlit as st
import sqlite3
from datetime import datetime
from pathlib import Path
import os

# ============ 配置 ============
DB_PATH = "requirements.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ============ 数据库初始化 ============
def init_db():
    """初始化数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK(role IN ('sales', 'researcher', 'admin'))
        )
    """)
    
    # 需求表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            org_name TEXT,
            sales_id INTEGER,
            researcher_id INTEGER,
            status TEXT DEFAULT '待处理' CHECK(status IN ('待处理', '处理中', '已完成')),
            result_note TEXT,
            result_file TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            completed_at DATETIME,
            FOREIGN KEY (sales_id) REFERENCES users(id),
            FOREIGN KEY (researcher_id) REFERENCES users(id)
        )
    """)
    
    # 插入一些测试用户（如果不存在）
    test_users = [
        ("张销售", "sales"),
        ("李销售", "sales"),
        ("王研究员", "researcher"),
        ("赵研究员", "researcher"),
        ("管理员", "admin"),
    ]
    for name, role in test_users:
        cursor.execute("INSERT OR IGNORE INTO users (name, role) VALUES (?, ?)", (name, role))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============ 数据库操作 ============
def get_users_by_role(role):
    """根据角色获取用户列表"""
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users WHERE role = ?", (role,)).fetchall()
    conn.close()
    return users

def get_all_users():
    """获取所有用户"""
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return users

def create_requirement(title, description, org_name, sales_id, researcher_id):
    """创建新需求"""
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO requirements (title, description, org_name, sales_id, researcher_id)
        VALUES (?, ?, ?, ?, ?)
    """, (title, description, org_name, sales_id, researcher_id))
    conn.commit()
    conn.close()

def get_requirements_by_researcher(researcher_id):
    """获取分配给某研究员的需求"""
    conn = get_db_connection()
    reqs = conn.execute("""
        SELECT r.*, 
               s.name as sales_name,
               re.name as researcher_name
        FROM requirements r
        LEFT JOIN users s ON r.sales_id = s.id
        LEFT JOIN users re ON r.researcher_id = re.id
        WHERE r.researcher_id = ?
        ORDER BY r.created_at DESC
    """, (researcher_id,)).fetchall()
    conn.close()
    return reqs

def get_all_requirements():
    """获取所有需求（管理员视角）"""
    conn = get_db_connection()
    reqs = conn.execute("""
        SELECT r.*, 
               s.name as sales_name,
               re.name as researcher_name
        FROM requirements r
        LEFT JOIN users s ON r.sales_id = s.id
        LEFT JOIN users re ON r.researcher_id = re.id
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()
    return reqs

def update_requirement_status(req_id, status, result_note=None, result_file=None):
    """更新需求状态"""
    conn = get_db_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if status == "已完成":
        conn.execute("""
            UPDATE requirements 
            SET status = ?, result_note = ?, result_file = ?, 
                updated_at = ?, completed_at = ?
            WHERE id = ?
        """, (status, result_note, result_file, now, now, req_id))
    else:
        conn.execute("""
            UPDATE requirements 
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status, now, req_id))
    
    conn.commit()
    conn.close()

def get_requirement_by_id(req_id):
    """根据ID获取需求详情"""
    conn = get_db_connection()
    req = conn.execute("""
        SELECT r.*, 
               s.name as sales_name,
               re.name as researcher_name
        FROM requirements r
        LEFT JOIN users s ON r.sales_id = s.id
        LEFT JOIN users re ON r.researcher_id = re.id
        WHERE r.id = ?
    """, (req_id,)).fetchone()
    conn.close()
    return req

def get_statistics():
    """获取统计数据"""
    conn = get_db_connection()
    
    # 按状态统计
    status_stats = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM requirements
        GROUP BY status
    """).fetchall()
    
    # 按研究员统计
    researcher_stats = conn.execute("""
        SELECT u.name, 
               COUNT(*) as total,
               SUM(CASE WHEN r.status = '已完成' THEN 1 ELSE 0 END) as completed
        FROM requirements r
        JOIN users u ON r.researcher_id = u.id
        GROUP BY r.researcher_id
    """).fetchall()
    
    # 按机构统计
    org_stats = conn.execute("""
        SELECT org_name, COUNT(*) as count
        FROM requirements
        WHERE org_name IS NOT NULL AND org_name != ''
        GROUP BY org_name
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()
    
    conn.close()
    return {
        "status": status_stats,
        "researcher": researcher_stats,
        "org": org_stats
    }

# ============ 页面组件 ============
def sales_page():
    """销售人员页面 - 提交需求"""
    st.header("📝 提交需求")
    
    with st.form("requirement_form"):
        title = st.text_input("事项名称 *", placeholder="请输入需求标题")
        description = st.text_area("事项描述", placeholder="详细描述需求内容...")
        org_name = st.text_input("机构名称", placeholder="客户机构名称")
        
        # 获取研究员列表
        researchers = get_users_by_role("researcher")
        researcher_options = {u["name"]: u["id"] for u in researchers}
        selected_researcher = st.selectbox(
            "指派研究人员 *",
            options=list(researcher_options.keys())
        )
        
        submitted = st.form_submit_button("提交需求", type="primary")
        
        if submitted:
            if not title:
                st.error("请填写事项名称！")
            elif not selected_researcher:
                st.error("请选择研究人员！")
            else:
                sales_id = st.session_state.current_user["id"]
                researcher_id = researcher_options[selected_researcher]
                create_requirement(title, description, org_name, sales_id, researcher_id)
                st.success(f"✅ 需求已提交，已指派给 {selected_researcher}")
                st.balloons()

def researcher_page():
    """研究人员页面 - 处理需求"""
    st.header("📋 我的待办")
    
    researcher_id = st.session_state.current_user["id"]
    reqs = get_requirements_by_researcher(researcher_id)
    
    if not reqs:
        st.info("暂无分配给您的需求")
        return
    
    # 按状态筛选
    status_filter = st.selectbox(
        "筛选状态",
        ["全部", "待处理", "处理中", "已完成"]
    )
    
    for req in reqs:
        if status_filter != "全部" and req["status"] != status_filter:
            continue
            
        status_color = {
            "待处理": "🔴",
            "处理中": "🟡", 
            "已完成": "🟢"
        }
        
        with st.expander(f"{status_color.get(req['status'], '⚪')} {req['title']} - {req['status']}"):
            st.write(f"**机构：** {req['org_name'] or '未填写'}")
            st.write(f"**提交人：** {req['sales_name']}")
            st.write(f"**提交时间：** {req['created_at']}")
            st.write(f"**描述：** {req['description'] or '无'}")
            
            if req["status"] == "已完成":
                st.write(f"**完成说明：** {req['result_note'] or '无'}")
                if req["result_file"]:
                    st.write(f"**结果文件：** {req['result_file']}")
            else:
                st.divider()
                col1, col2 = st.columns(2)
                
                with col1:
                    if req["status"] == "待处理":
                        if st.button("开始处理", key=f"start_{req['id']}"):
                            update_requirement_status(req["id"], "处理中")
                            st.rerun()
                
                with col2:
                    if req["status"] in ["待处理", "处理中"]:
                        with st.form(f"complete_form_{req['id']}"):
                            result_note = st.text_area("完成情况说明")
                            uploaded_file = st.file_uploader("上传结果文件")
                            
                            if st.form_submit_button("标记完成"):
                                file_path = None
                                if uploaded_file:
                                    file_path = UPLOAD_DIR / f"{req['id']}_{uploaded_file.name}"
                                    with open(file_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    file_path = str(file_path)
                                
                                update_requirement_status(
                                    req["id"], "已完成", 
                                    result_note, file_path
                                )
                                st.success("已完成！")
                                st.rerun()

def admin_page():
    """管理员页面 - 总览和统计"""
    st.header("📊 管理后台")
    
    tab1, tab2, tab3 = st.tabs(["需求列表", "数据统计", "用户管理"])
    
    with tab1:
        st.subheader("所有需求")
        reqs = get_all_requirements()
        
        # 筛选器
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("状态", ["全部", "待处理", "处理中", "已完成"], key="admin_status")
        with col2:
            researchers = get_users_by_role("researcher")
            researcher_names = ["全部"] + [u["name"] for u in researchers]
            researcher_filter = st.selectbox("研究员", researcher_names)
        with col3:
            search_keyword = st.text_input("搜索关键词")
        
        for req in reqs:
            # 应用筛选
            if status_filter != "全部" and req["status"] != status_filter:
                continue
            if researcher_filter != "全部" and req["researcher_name"] != researcher_filter:
                continue
            if search_keyword and search_keyword.lower() not in (req["title"] + (req["description"] or "")).lower():
                continue
            
            status_color = {"待处理": "🔴", "处理中": "🟡", "已完成": "🟢"}
            
            with st.expander(f"{status_color.get(req['status'], '⚪')} [{req['id']}] {req['title']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**状态：** {req['status']}")
                    st.write(f"**机构：** {req['org_name'] or '未填写'}")
                    st.write(f"**提交人：** {req['sales_name']}")
                with col2:
                    st.write(f"**处理人：** {req['researcher_name']}")
                    st.write(f"**创建时间：** {req['created_at']}")
                    if req["completed_at"]:
                        st.write(f"**完成时间：** {req['completed_at']}")
                
                st.write(f"**描述：** {req['description'] or '无'}")
                
                if req["result_note"]:
                    st.write(f"**完成说明：** {req['result_note']}")
                if req["result_file"]:
                    file_path = Path(req["result_file"])
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            st.download_button(
                                "📥 下载结果文件",
                                f.read(),
                                file_name=file_path.name,
                                key=f"download_{req['id']}"
                            )
    
    with tab2:
        st.subheader("数据统计")
        stats = get_statistics()
        
        # 状态分布
        col1, col2, col3 = st.columns(3)
        status_dict = {s["status"]: s["count"] for s in stats["status"]}
        with col1:
            st.metric("待处理", status_dict.get("待处理", 0))
        with col2:
            st.metric("处理中", status_dict.get("处理中", 0))
        with col3:
            st.metric("已完成", status_dict.get("已完成", 0))
        
        st.divider()
        
        # 研究员工作量
        st.subheader("研究员工作量")
        if stats["researcher"]:
            for r in stats["researcher"]:
                progress = r["completed"] / r["total"] if r["total"] > 0 else 0
                st.write(f"**{r['name']}**: {r['completed']}/{r['total']} 完成")
                st.progress(progress)
        
        st.divider()
        
        # 机构统计
        st.subheader("机构需求 Top 10")
        if stats["org"]:
            for org in stats["org"]:
                st.write(f"- {org['org_name']}: {org['count']} 个需求")
    
    with tab3:
        st.subheader("用户管理")
        users = get_all_users()
        
        role_names = {"sales": "销售", "researcher": "研究员", "admin": "管理员"}
        for user in users:
            st.write(f"- **{user['name']}** ({role_names.get(user['role'], user['role'])})")
        
        st.divider()
        st.subheader("添加新用户")
        with st.form("add_user_form"):
            new_name = st.text_input("姓名")
            new_role = st.selectbox("角色", ["sales", "researcher", "admin"], 
                                   format_func=lambda x: role_names.get(x, x))
            if st.form_submit_button("添加"):
                if new_name:
                    conn = get_db_connection()
                    try:
                        conn.execute("INSERT INTO users (name, role) VALUES (?, ?)", 
                                   (new_name, new_role))
                        conn.commit()
                        st.success(f"已添加用户: {new_name}")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("用户名已存在")
                    finally:
                        conn.close()

# ============ 主程序 ============
def main():
    st.set_page_config(
        page_title="需求管理系统",
        page_icon="📋",
        layout="wide"
    )
    
    # 初始化数据库
    init_db()
    
    # 侧边栏 - 用户选择（简化版登录）
    st.sidebar.title("📋 需求管理系统")
    st.sidebar.divider()
    
    # 用户选择
    users = get_all_users()
    user_options = {f"{u['name']} ({u['role']})": dict(u) for u in users}
    
    selected_user_key = st.sidebar.selectbox(
        "选择当前用户",
        options=list(user_options.keys()),
        help="实际项目中这里应该是登录功能"
    )
    
    if selected_user_key:
        st.session_state.current_user = user_options[selected_user_key]
        current_user = st.session_state.current_user
        
        st.sidebar.write(f"👤 当前用户: **{current_user['name']}**")
        st.sidebar.write(f"🏷️ 角色: **{current_user['role']}**")
        st.sidebar.divider()
        
        # 根据角色显示不同页面
        if current_user["role"] == "sales":
            sales_page()
        elif current_user["role"] == "researcher":
            researcher_page()
        elif current_user["role"] == "admin":
            admin_page()
    
    # 页脚
    st.sidebar.divider()
    st.sidebar.caption("轻量级需求管理系统 v1.0")

if __name__ == "__main__":
    main()

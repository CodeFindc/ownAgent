const translations = {
    "en": {
        "nav_messages": "Messages",
        "nav_users": "Users",
        "nav_profile": "Profile",
        "nav_settings": "Settings",
        "user_profile": "My Profile",
        "user_management": "User Management",
        "platform_settings": "Platform Settings",
        "logout": "Logout",
        "chat_header": "Agent Session",
        "my_profile_header": "My Profile",
        "platform_settings_header": "Platform Settings",
        "user_management_header": "User Management",
        "save_profile": "Save Profile Info",
        "security": "Security",
        "current_password": "Current Password",
        "new_password": "New Password",
        "confirm_password": "Confirm New Password",
        "update_password": "Update Password",
        "change_avatar": "Change",
        "username": "Username",
        "email": "Email",
        "general_settings": "General Settings",
        "site_name": "Site Name",
        "logo_text": "Logo Text (Short)",
        "allow_registration": "Allow User Registration",
        "save_settings": "Save Settings",
        "system_language": "System Language",
        "new_chat": "New Chat",
        "history": "HISTORY",
        "type_message": "Type your message...",
        "create_user": "Create New User",
        "role": "Role",
        "is_active": "Active",
        "actions": "Actions",
        "edit": "Edit",
        "reset_password": "Reset Password",
        "loading": "Loading...",
        "uploading": "Uploading...",
        "saved": "Saved!",
        "error": "Error occurred.",
        "delete_confirm": "Confirm?",
        "login_title": "Login to OwnAgent",
        "login_button": "Login",
        "register_link": "No account? Register here",
        "register_title": "Register",
        "register_button": "Register",
        "login_link": "Have an account? Login here",
        "you": "You",
        "delete": "Delete",
        "actions": "Actions",
        "session_deleted": "Session deleted. Please create or select a session.",
        "no_history": "No history",
        "delete_confirm_short": "Confirm?",
        "delete_confirm_short": "Confirm?",
        "custom_answer": "Custom Answer",
        "new_session_welcome": "Ready for a new task."
    },
    "cn": {
        "nav_messages": "消息",
        "nav_users": "用户管理",
        "nav_profile": "个人资料",
        "nav_settings": "设置",
        "user_profile": "我的资料",
        "user_management": "用户管理",
        "platform_settings": "平台设置",
        "logout": "退出登录",
        "chat_header": "智能会话",
        "my_profile_header": "我的资料",
        "platform_settings_header": "平台设置",
        "user_management_header": "用户管理中心",
        "save_profile": "保存资料",
        "security": "安全设置",
        "current_password": "当前密码",
        "new_password": "新密码",
        "confirm_password": "确认新密码",
        "update_password": "更新密码",
        "change_avatar": "更换",
        "username": "用户名",
        "email": "邮箱",
        "general_settings": "通用设置",
        "site_name": "站点名称",
        "logo_text": "Logo文本(简短)",
        "allow_registration": "允许用户注册",
        "save_settings": "保存设置",
        "system_language": "系统语言",
        "new_chat": "新建会话",
        "history": "历史记录",
        "type_message": "输入消息...",
        "create_user": "新建用户",
        "role": "角色",
        "is_active": "状态",
        "actions": "操作",
        "edit": "编辑",
        "reset_password": "重置密码",
        "loading": "加载中...",
        "uploading": "上传中...",
        "saved": "已保存!",
        "error": "发生错误。",
        "delete_confirm": "确认删除?",
        "login_title": "登录 OwnAgent",
        "login_button": "登录",
        "register_link": "没有账号？点击注册",
        "register_title": "注册账号",
        "register_button": "注册",
        "login_link": "已有账号？点击登录",
        "you": "你",
        "delete": "删除",
        "actions": "操作",
        "session_deleted": "会话已删除。请新建或选择一个会话。",
        "no_history": "暂无历史",
        "delete_confirm_short": "确认?",
        "custom_answer": "自定义回答",
        "new_session_welcome": "准备好开始新的任务了。"
    }
};

// Make available globally
window.translations = translations;
window.currentLanguage = localStorage.getItem('app_language') || 'en';

function t(key) {
    const lang = window.currentLanguage;
    if (translations[lang] && translations[lang][key]) {
        return translations[lang][key];
    }
    return key; // Fallback to key if not found
}

function setLanguage(lang) {
    if (!translations[lang]) return;
    window.currentLanguage = lang;
    localStorage.setItem('app_language', lang);
    applyTranslations();
}

function getLanguage() {
    return window.currentLanguage;
}

function applyTranslations() {
    const lang = window.currentLanguage;
    const t_dict = translations[lang];
    if (!t_dict) return;

    // 1. Text Content
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t_dict[key]) {
            el.textContent = t_dict[key];
        }
    });

    // 2. Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (t_dict[key]) {
            el.placeholder = t_dict[key];
        }
    });

    // 3. Update HTML lang attribute
    document.documentElement.lang = lang === 'cn' ? 'zh-CN' : 'en';
}

// Expose globals
window.t = t;
window.setLanguage = setLanguage;
window.getLanguage = getLanguage;
window.applyTranslations = applyTranslations;

// Auto-init
document.addEventListener('DOMContentLoaded', () => {
    applyTranslations();
});

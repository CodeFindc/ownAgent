document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    const forms = document.querySelectorAll('.auth-form');
    const msgBox = document.getElementById('msg-box');

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            forms.forEach(f => f.classList.remove('active'));

            tab.classList.add('active');
            const targetId = tab.dataset.target + '-form';
            document.getElementById(targetId).classList.add('active');

            clearMsg();
        });
    });

    // Helper: Show Message
    function showMsg(type, text) {
        msgBox.className = 'msg-box'; // reset
        msgBox.classList.add(type === 'error' ? 'msg-error' : 'msg-success');
        msgBox.textContent = text;
        msgBox.style.display = 'block';
    }

    function clearMsg() {
        msgBox.style.display = 'none';
    }

    // Login Logic
    document.getElementById('form-login').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearMsg();
        const formData = new FormData(e.target);

        try {
            const res = await fetch('/auth/token', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Login failed');
            }

            const data = await res.json();
            localStorage.setItem('access_token', data.access_token);
            window.location.href = '/'; // Redirect to main app
        } catch (err) {
            showMsg('error', err.message);
        }
    });

    // Register Logic
    document.getElementById('form-register').addEventListener('submit', async (e) => {
        e.preventDefault();
        clearMsg();

        const username = e.target.username.value;
        const password = e.target.password.value;
        const confirm = e.target.confirm_password.value;

        if (password !== confirm) {
            showMsg('error', "Passwords do not match");
            return;
        }

        try {
            const res = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Registration failed');
            }

            // Success
            showMsg('success', 'Account created! Please login.');
            e.target.reset();

            // Switch to login tab after 1.5s
            setTimeout(() => {
                document.querySelector('[data-target="login"]').click();
            }, 1500);

        } catch (err) {
            showMsg('error', err.message);
        }
    });
});

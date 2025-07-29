const Dashboard = (function(){

    // 随机颜色生成函数
    function generateRandomColor() {
        const letters = '89ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * letters.length)];
        }
        return color;
    }

    // 初始化用户恒星
    function initUserStar() {
        const userStar = document.getElementById('user-star');
        const starColor = generateRandomColor();
        userStar.style.backgroundColor = starColor;

        // 添加点击事件：进入user info界面（后续开发）
        userStar.addEventListener('click', function(){
            window.location.href = '/user_info';  // 假设这是未来用户信息页面的路径
        });
    }

    // 初始化函数
    function init() {
        initUserStar();
    }

    // 公共接口
    return {
        init: init
    };

})();

// 页面加载后自动执行
window.onload = Dashboard.init;

# ProductShot Agent Frontend

Vue 3 + TypeScript + Vite 前端，使用 Pinia、Vue Router、Axios 和 Element Plus。

## 安装

```bash
cd frontend
npm install
```

## 启动

```bash
npm run dev
```

默认访问 `http://127.0.0.1:5173`。

## 环境变量

可在 `frontend/.env.local` 配置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 页面

- 首页：产品定位和项目入口。
- 商品工作台：在一个按阶段的界面内完成商品与原图确认、原图理解确认、商品策略、创意方向、素材生成和交付。
- 任务中心：查看各项目独立运行的出图任务。
- 模型管理：配置非敏感模型参数。

工作台将平台与风格选择放在创意规划阶段，支持小红书、朋友圈、淘宝、闲鱼及多种风格的多选或不选；交付阶段只提供图片下载与文案复制。

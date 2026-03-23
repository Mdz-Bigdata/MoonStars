# 创建本地环境变量文件
cp backend/.env.example backend/.env

echo "请编辑 backend/.env 文件，配置数据库连接"
echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/blog_converter"

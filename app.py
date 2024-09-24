# app.py (保持之前功能不变，修复 apply_resources 路由问题)
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resources.db'
db = SQLAlchemy(app)

# 资源模型
class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_type = db.Column(db.String(50), nullable=False)
    resource_name = db.Column(db.String(100), nullable=False)
    resource_address = db.Column(db.String(100), nullable=False)


# 首页
@app.route('/')
def index():
    return render_template('index.html')

# 管理资源页面
@app.route('/manage_resources', methods=['GET', 'POST'])
def manage_resources():
    if request.method == 'POST':
        password = request.form['admin_password']
        if password != 'intchains':
            flash('管理员密码错误！', 'danger')
            return redirect(url_for('manage_resources'))

        action = request.form['action']
        if action == 'add':
            new_resource = Resource(
                resource_type=request.form['resource_type'],
                resource_name=request.form['resource_name'],
                resource_address=request.form['resource_address']
            )
            db.session.add(new_resource)
            db.session.commit()
            flash('资源添加成功！', 'success')
        elif action == 'delete':
            resource_name = request.form['resource_name']
            resource = Resource.query.filter_by(resource_name=resource_name).first()
            if resource:
                db.session.delete(resource)
                db.session.commit()
                flash('资源删除成功！', 'success')
            else:
                flash('资源未找到！', 'warning')
        return redirect(url_for('manage_resources'))

    return render_template('manage_resources.html')

# 申请资源页面（新定义的路由）
@app.route('/apply_resources', methods=['GET', 'POST'])
def apply_resources():
    if request.method == 'POST':
        resource_name = request.form['resource_name']
        resource = Resource.query.filter_by(resource_name=resource_name).first()
        if resource:
            flash(f'{resource_name} 已成功申请！', 'success')
        else:
            flash(f'资源 {resource_name} 不存在！', 'warning')
        return redirect(url_for('apply_resources'))
    return render_template('apply_resources.html')

# 查看资源页面
@app.route('/view_resources')
def view_resources():
    # 从数据库中按资源类型分类展示资源
    resources_by_type = {}
    resources = Resource.query.all()
    
    for resource in resources:
        if resource.resource_type not in resources_by_type:
            resources_by_type[resource.resource_type] = []
        resources_by_type[resource.resource_type].append(resource)
    
    return render_template('view_resources.html', resources_by_type=resources_by_type)

# 使用报表页面
@app.route('/usage_report')
def usage_report():
    # 这里可以添加获取并显示资源使用报表的逻辑
    return render_template('usage_report.html')

# 初始化数据库
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

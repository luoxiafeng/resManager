from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resources.db'
db = SQLAlchemy(app)
#migrate = Migrate(app, db)
# 资源模型
class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_type = db.Column(db.String(50), nullable=False)
    resource_name = db.Column(db.String(100), nullable=False)
    resource_address = db.Column(db.String(100), nullable=False)
    is_busy = db.Column(db.Boolean, default=False)
    assigned_to = db.Column(db.String(100), nullable=True)
    assigned_time = db.Column(db.DateTime, nullable=True)

# 资源排队模型
class Queue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_name = db.Column(db.String(100), nullable=False)  # 申请人名称字段
    resource_type = db.Column(db.String(50), nullable=False)
    fpga_name = db.Column(db.String(100), nullable=True)  # 如果是FPGA
    fpga_address = db.Column(db.String(100), nullable=True)
    apply_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False)

# 首页
@app.route('/')
def index():
    return render_template('index.html')

# 管理资源页面
@app.route('/manage_resources', methods=['GET', 'POST'])
def manage_resources():
    if request.method == 'POST':
        action = request.form['action']

        if action == 'add':
            password = request.form['admin_password']
            if password != 'intchains':
                flash('管理员密码错误！', 'danger')
                return redirect(url_for('manage_resources'))

            # 添加资源逻辑
            new_resource = Resource(
                resource_type=request.form['resource_type'],
                resource_name=request.form['resource_name'],
                resource_address=request.form['resource_address']
            )
            db.session.add(new_resource)
            db.session.commit()
            flash('资源添加成功！', 'success')

        elif action == 'delete':
            password = request.form['admin_password']
            if password != 'intchains':
                flash('管理员密码错误！', 'danger')
                return redirect(url_for('manage_resources'))

            # 删除资源逻辑
            resource_name = request.form['resource_name']
            resource = Resource.query.filter_by(resource_name=resource_name).first()
            if resource:
                db.session.delete(resource)
                db.session.commit()
                flash('资源删除成功！', 'success')
            else:
                flash('资源未找到！', 'warning')

        elif action == 'release':
            # 释放资源逻辑，无需密码
            resource_name = request.form['resource_name']
            resource = Resource.query.filter_by(resource_name=resource_name).first()
            if resource and resource.is_busy:
                resource.is_busy = False
                resource.assigned_to = None
                resource.assigned_time = None
                db.session.commit()
                flash(f'资源 {resource_name} 已释放！', 'success')
            else:
                flash(f'资源 {resource_name} 不存在或当前空闲！', 'warning')

        return redirect(url_for('manage_resources'))

    return render_template('manage_resources.html')

# 申请资源页面
@app.route('/apply_resources', methods=['GET', 'POST'])
def apply_resources():
    if request.method == 'POST':
        if 'queue' in request.form:  # 当点击排队按钮时执行
            # 查询第一个排队的用户并检查资源是否空闲
            first_in_queue = Queue.query.first()
            if first_in_queue:
                # 检查是否有空闲资源
                resource = Resource.query.filter_by(resource_type=first_in_queue.resource_type, is_busy=False).first()
                if resource:
                    # 分配资源给排队中的用户
                    resource.is_busy = True
                    resource.assigned_to = first_in_queue.applicant_name
                    resource.assigned_time = datetime.utcnow()
                    db.session.delete(first_in_queue)  # 删除该排队记录
                    db.session.commit()
                    flash(f'{resource.resource_type} 资源已分配给 {first_in_queue.applicant_name}！', 'success')
                else:
                    flash('当前无空闲资源。', 'warning')
            return redirect(url_for('apply_resources'))

        # 处理申请资源逻辑
        resource_type = request.form['resource_type']
        applicant_name = request.form['applicant_name']
        usage_time = request.form['usage_time']

        if resource_type == 'FPGA':
            fpga_name = request.form['fpga_name']
            fpga_address = request.form['fpga_address']
            resource = Resource.query.filter_by(resource_name=fpga_name, resource_address=fpga_address).first()
        else:
            resource = Resource.query.filter_by(resource_type=resource_type).first()

        if resource and not resource.is_busy:
            # 分配资源
            resource.is_busy = True
            resource.assigned_to = applicant_name
            resource.assigned_time = datetime.utcnow()
            db.session.commit()
            flash(f'{resource_type} 资源已分配给 {applicant_name}！', 'success')
        else:
            # 创建新的排队记录
            new_queue = Queue(
                applicant_name=applicant_name,
                resource_type=resource_type,
                fpga_name=fpga_name,
                fpga_address=fpga_address,
                status='排队'
            )
            db.session.add(new_queue)
            db.session.commit()
            flash(f'{resource_type} 资源正忙，{applicant_name} 已进入排队。', 'warning')

        return redirect(url_for('apply_resources'))

    # 查询所有排队的用户
    queued_users = Queue.query.all()

    # 查询所有 FPGA 资源
    fpga_resources = Resource.query.filter_by(resource_type='FPGA').all()

    return render_template('apply_resources.html', queued_users=queued_users, fpga_resources=fpga_resources)

# 释放资源时，从排队列表中选取第一个用户
@app.route('/release_resource/<int:resource_id>')
def release_resource(resource_id):
    resource = Resource.query.get(resource_id)
    if resource:
        resource.is_busy = False
        resource.assigned_to = None
        resource.assigned_time = None
        db.session.commit()

        # 从排队中选择第一个用户分配资源
        next_in_queue = Queue.query.filter_by(resource_type=resource.resource_type).first()
        if next_in_queue:
            resource.is_busy = True
            resource.assigned_to = next_in_queue.applicant_name
            resource.assigned_time = datetime.utcnow()
            db.session.delete(next_in_queue)  # 删除该排队记录
            db.session.commit()
            flash(f'{resource.resource_type} 资源已分配给 {next_in_queue.applicant_name}！', 'success')
        else:
            flash(f'{resource.resource_type} 资源已释放，当前无排队用户。', 'success')

    return redirect(url_for('view_resources'))

# 新增队列路由，检查是否有资源空闲并分配资源
@app.route('/queue_resource', methods=['POST'])
def queue_resource():
    # 查询是否有空闲资源
    free_resource = Resource.query.filter_by(is_busy=False).first()

    if free_resource:
        # 获取排队中第一个用户
        first_user_in_queue = Queue.query.first()

        if first_user_in_queue:
            # 分配资源给排队中第一个用户
            free_resource.is_busy = True
            free_resource.assigned_to = first_user_in_queue.applicant_name  # 记录资源占用者
            free_resource.assigned_time = datetime.now()  # 记录资源占用时间
            db.session.commit()

            # 从队列中移除这个用户
            db.session.delete(first_user_in_queue)
            db.session.commit()

            flash(f"资源已分配给 {first_user_in_queue.applicant_name}", 'success')
        else:
            flash("没有用户在排队", 'info')
    else:
        flash("没有空闲资源", 'warning')

    return redirect(url_for('apply_resources'))

# 查看资源页面
@app.route('/view_resources')
def view_resources():
    resources = Resource.query.all()
    for resource in resources:
        if resource.is_busy and resource.assigned_time:
            # 计算占用时长
            resource.usage_duration = datetime.now() - resource.assigned_time
        else:
            resource.usage_duration = None
    return render_template('view_resources.html', resources=resources)


# 使用报表页面
@app.route('/usage_report')
def usage_report():
    return render_template('usage_report.html')

# 分配下一个排队资源
def assign_next_resource():
    next_in_queue = Queue.query.order_by(Queue.apply_time).first()
    if next_in_queue:
        # 分配资源
        resource = Resource.query.filter_by(resource_type=next_in_queue.resource_type, is_busy=False).first()
        if resource:
            resource.is_busy = True
            resource.assigned_to = next_in_queue.applicant_name
            resource.assigned_time = datetime.utcnow()
            db.session.delete(next_in_queue)  # 从队列中删除
            db.session.commit()

# 初始化数据库
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)

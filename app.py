from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from datetime import datetime

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
    is_busy = db.Column(db.Boolean, default=False)  # 资源是否被占用
    assigned_to = db.Column(db.String(100), nullable=True)  # 当前占用资源的用户
    assigned_time = db.Column(db.DateTime, nullable=True)  # 资源分配时间
    usage_duration = db.Column(db.Integer, nullable=True)  # 使用时长（分钟）

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
        resource_name = request.form['resource_name']
        resource_address = request.form['resource_address']
        resource_type = request.form['resource_type']

        # 处理资源释放
        if action == 'release':
            owner_name = request.form['owner_name']
            resource = Resource.query.filter_by(resource_name=resource_name, resource_address=resource_address).first()

            if resource:
                if resource.is_busy and resource.assigned_to == owner_name:
                    # 释放资源
                    resource.is_busy = False
                    resource.assigned_to = None
                    resource.assigned_time = None
                    db.session.commit()
                    flash(f'资源 {resource_name} 成功释放！', 'success')
                else:
                    flash(f'资源 {resource_name} 不是由 {owner_name} 占用，无法释放！', 'danger')
            else:
                flash('资源未找到！', 'warning')

            return redirect(url_for('manage_resources'))

        # 其他处理逻辑保持不变
        password = request.form['admin_password']
        if password != 'intchains':
            flash('管理员密码错误！', 'danger')
            return redirect(url_for('manage_resources'))

        if action == 'add':
            new_resource = Resource(
                resource_type=resource_type,
                resource_name=resource_name,
                resource_address=resource_address
            )
            db.session.add(new_resource)
            db.session.commit()
            flash('资源添加成功！', 'success')

        elif action == 'delete':
            resource = Resource.query.filter_by(resource_name=resource_name).first()
            if resource:
                db.session.delete(resource)
                db.session.commit()
                flash('资源删除成功！', 'success')
            else:
                flash('资源未找到！', 'warning')

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
        # 先检查资源是否存在
        existing_resource = Resource.query.filter_by(resource_type=resource_type,
                                                     resource_name=fpga_name,
                                                     resource_address=fpga_address).first()

        if not existing_resource:
            flash(f'资源不存在：{resource_type} {fpga_name} {fpga_address}', 'danger')
            return redirect(url_for('apply_resources'))
        # 检查是否已有相同申请人和资源的排队信息
        existing_queue = Queue.query.filter_by(applicant_name=applicant_name,
                                               resource_type=resource_type,
                                               fpga_name=fpga_name,
                                               fpga_address=fpga_address).first()
        if existing_queue:
            flash('已经在排队同类资源，不要重复排队', 'danger')
            return redirect(url_for('apply_resources'))
        
        if resource and not resource.is_busy:
            # 分配资源
            resource.is_busy = True
            resource.assigned_to = applicant_name
            resource.assigned_time = datetime.now()
            resource.usage_duration = usage_time
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
from datetime import datetime

# 资源查看页面，显示资源的状态以及占用者的信息
@app.route('/view_resources')
def view_resources():
    resources = Resource.query.all()

    # 创建一个新的列表用于存储处理过的资源信息
    processed_resources = []

    for resource in resources:
        resource_info = {
            'resource_type': resource.resource_type,
            'resource_name': resource.resource_name,
            'resource_address': resource.resource_address,
            'is_busy': resource.is_busy,
            'assigned_to': resource.assigned_to,
            'assigned_time': resource.assigned_time,
            'usage_duration': resource.usage_duration
        }

        # 如果资源被占用，计算占用时长
        if resource.is_busy and resource.assigned_time:
            # 使用当前时间减去分配时间来计算占用时长
            now = datetime.now()
            duration = now - resource.assigned_time
            # 计算占用的分钟数
            duration_in_minutes = int(duration.total_seconds() // 60)
            # 确保至少显示1分钟
            if duration_in_minutes < 1:
                duration_in_minutes = 1
            resource_info['occupied_duration'] = f"{duration_in_minutes} 分钟"
        else:
            resource_info['occupied_duration'] = "空闲"

        processed_resources.append(resource_info)

    return render_template('view_resources.html', resources=processed_resources)


# 使用报表页面
@app.route('/usage_report', methods=['GET', 'POST'])
def usage_report():
    user_labels = []
    usage_data = []

    if request.method == 'POST':
        # 获取表单中的时间段
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']

        # 将字符串转换为 datetime 对象
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        # 查询在时间段内成功占用资源的记录
        results = db.session.query(Queue.applicant_name, db.func.sum(db.func.julianday(Queue.end_time) - db.func.julianday(Queue.assigned_time)).label('total_duration')) \
                            .filter(Queue.status == '申请到') \
                            .filter(Queue.assigned_time >= start_date) \
                            .filter(Queue.end_time <= end_date) \
                            .group_by(Queue.applicant_name).all()

        # 将查询结果转换为图表所需的数据
        for result in results:
            user_labels.append(result.applicant_name)
            # 将结果转换为分钟数
            total_duration_minutes = result.total_duration * 24 * 60
            usage_data.append(total_duration_minutes)

    return render_template('usage_report.html', user_labels=user_labels, usage_data=usage_data)

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
    app.run(host='0.0.0.0', port=5000, debug=True)

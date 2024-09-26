from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from datetime import datetime
from threading import Thread
from datetime import datetime, timedelta
from sqlalchemy import UniqueConstraint
from flask import jsonify
import time

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
    __table_args__ = (UniqueConstraint('resource_name', 'resource_address', name='uix_resource_name_address'),)
# 资源排队模型
class Queue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    applicant_name = db.Column(db.String(100), nullable=False)  # 申请人名称字段
    resource_type = db.Column(db.String(50), nullable=False)
    fpga_name = db.Column(db.String(100), nullable=True)  # 如果是FPGA
    fpga_address = db.Column(db.String(100), nullable=True)
    apply_time = db.Column(db.DateTime, default=datetime.now)
    usage_duration = db.Column(db.Integer, nullable=True)  # 使用时长（分钟）
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
                    resource.usage_duration = None
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
            try:
                db.session.add(new_resource)
                db.session.commit()
                flash('资源添加成功！', 'success')
            except:
                db.session.rollback()
                flash('error！', 'warning')

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
        # 处理申请资源逻辑
        resource_type = request.form['resource_type']
        applicant_name = request.form['applicant_name']
        usage_time = request.form['usage_time']

        if resource_type == 'FPGA':
            fpga_name = request.form['fpga_name']
            fpga_address = request.form['fpga_address']
            resource = Resource.query.filter_by(resource_name=fpga_name, resource_address=fpga_address).first()
            
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
        # 创建新的排队记录
        new_queue = Queue(
            applicant_name=applicant_name,
            resource_type=resource_type,
            fpga_name=fpga_name,
            fpga_address=fpga_address,
            usage_duration=usage_time,
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
            resource.assigned_time = datetime.now()
            db.session.delete(next_in_queue)  # 删除该排队记录
            db.session.commit()
            flash(f'{resource.resource_type} 资源已分配给 {next_in_queue.applicant_name}！', 'success')
        else:
            flash(f'{resource.resource_type} 资源已释放，当前无排队用户。', 'success')

    return redirect(url_for('view_resources'))

# 新增队列路由，检查是否有资源空闲并分配资源
@app.route('/queue_resource', methods=['POST'])
def queue_resource():
    # 获取所有排队中的用户
    all_users_in_queue = Queue.query.all()
    
    if all_users_in_queue:
        for user_in_queue in all_users_in_queue:
            # 查找该用户申请的空闲资源
            free_resource = Resource.query.filter_by(resource_name=user_in_queue.fpga_name, resource_address=user_in_queue.fpga_address, is_busy=False).first()

            if free_resource:
                # 分配资源给该排队用户
                free_resource.is_busy = True
                free_resource.assigned_to = user_in_queue.applicant_name  # 记录资源占用者
                free_resource.assigned_time = datetime.now()  # 记录资源占用时间
                free_resource.usage_duration = user_in_queue.usage_duration
                db.session.commit()

                # 从队列中移除该用户
                db.session.delete(user_in_queue)
                db.session.commit()

                flash(f"资源已分配给 {user_in_queue.applicant_name}", 'success')
            else:
                flash(f"{user_in_queue.applicant_name} 请求的资源 ({user_in_queue.fpga_name}, {user_in_queue.fpga_address}) 暂时没有空闲。", 'info')
    else:
        flash("没有用户在排队", 'warning')

    return redirect(url_for('apply_resources'))

@app.route('/delete_queue', methods=['POST'])
def delete_queue():
    data = request.get_json()  # 从 JSON 请求体中获取数据
    applicant_name = data.get('applicant_name')
    fpga_name = data.get('fpga_name')
    fpga_address = data.get('fpga_address')

    if not applicant_name or not fpga_name or not fpga_address:
        return jsonify({'success': False, 'message': '缺少必要的参数'}), 400

    # 根据申请人、FPGA名称和地址来查找队列记录
    queue_entry = Queue.query.filter_by(applicant_name=applicant_name, fpga_name=fpga_name, fpga_address=fpga_address).first()

    if queue_entry:
        db.session.delete(queue_entry)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '未找到该排队记录'})


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
            resource.assigned_time = datetime.now()
            db.session.delete(next_in_queue)  # 从队列中删除
            db.session.commit()

# 资源释放的线程
def release_resources():
    with app.app_context():
        while True:
            # 查询所有被占用的资源
            busy_resources = Resource.query.filter_by(is_busy=True).all()
            for resource in busy_resources:
                if resource.assigned_time and resource.usage_duration:
                    # 从数据库中获取占用时长（已分配时间）
                    assigned_time = resource.assigned_time
                    current_time = datetime.now()

                    # 计算占用时长与申请时长的差值
                    usage_duration = timedelta(minutes=resource.usage_duration)
                    time_difference = current_time - assigned_time

                    # 如果占用时间超过申请的使用时长，则释放资源
                    if time_difference >= usage_duration:
                        resource.is_busy = False
                        resource.assigned_to = None
                        resource.assigned_time = None
                        resource.usage_duration = None
                        db.session.commit()
                        print(f"Resource {resource.resource_name} has been released due to timeout.")
            # 每隔60秒检查一次
            time.sleep(60)

# 在应用启动时启动该线程
def start_resource_monitor():
    resource_thread = Thread(target=release_resources)
    resource_thread.daemon = True  # 让线程随主程序一起退出
    resource_thread.start()


if __name__ == '__main__':
    # 初始化数据库
    with app.app_context():
        db.create_all()
    start_resource_monitor()
    app.run(host='0.0.0.0', port=5000, debug=True)

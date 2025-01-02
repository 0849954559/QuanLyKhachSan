
import hashlib
import math

from flask_login import login_user, current_user, logout_user, login_required
from flask import render_template, request, redirect, session, jsonify, Flask, url_for, flash
import dao
from hotelapp import app, admin,login, db
import cloudinary.uploader
from models import RoomType, Room, UserEnum, User, Guest, RoomDetail
from werkzeug.security import generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


@app.route('/search_rooms', methods=['POST'])
def search_rooms():
    room_type_id = int(request.form.get('room_type'))
    check_in_str = (request.form.get('check_in'))
    check_out_str = request.form.get('check_out')
    guests = int(request.form.get('guests'))

    # Đảm bảo định dạng ngày tháng của chuỗi (giả sử định dạng là "YYYY-MM-DD")
    check_in = datetime.strptime(check_in_str, "%Y-%m-%d").date()
    check_out = datetime.strptime(check_out_str, "%Y-%m-%d").date()

    available_rooms = dao.find_available_rooms(room_type_id, guests, check_in, check_out)

    return render_template('search_results.html', rooms=available_rooms)


@app.route('/')
def index():
    room_types = RoomType.query.all()
    q = request.args.get("q")
    cate_id = request.args.get("roomType_id")
    page = request.args.get("page")
    rooms = dao.load_rooms(q=q, cate_id=cate_id, page=page)
    pages = dao.count_room()
    return render_template('index.html', room_types=room_types, rooms=rooms,
                           pages=math.ceil(pages / app.config["PAGE_SIZE"]))


@app.route('/rooms/<int:id>')
def details(id):
    room = dao.load_room_by_id(id)
    return render_template('room-details.html', room=room)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['email']  # dùng email làm username
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Mật khẩu và xác nhận mật khẩu không khớp!', 'danger')
            return redirect(url_for('register'))

        # Hash mật khẩu trước khi lưu
        hashed_password = str(hashlib.md5(password.encode('utf-8')).hexdigest())

        new_user = User(
            name=name,
            username=username,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Đăng ký thành công!', 'success')
        return redirect(url_for('register'))

    return render_template('register.html')


from werkzeug.utils import redirect


@app.route('/login', methods=['get', 'post'])
def login_my_user():
    err_msg = ""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')

            user = dao.auth_user(username=username, password=password)
            if user:
                login_user(user=user)

                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)

                if user.role == UserEnum.ADMIN:
                    return redirect('/admin')
                elif user.role == UserEnum.STAFF:
                    return redirect('/staff')
                else:
                    return redirect(url_for('index'))

            err_msg = "Sai tên đăng nhập hoặc mật khẩu"
        except Exception as ex:
            err_msg = str(ex)

    return render_template('login.html', err_msg=err_msg)



@app.route('/logout')
def logout_my_user():
    logout_user()
    return redirect('/login')




@app.context_processor
def common_attributes():
    return {
        "roomsType": dao.load_roomtypes()
    }


@login.user_loader
def load_user(user_id):
    return dao.get_user_by_id(user_id=user_id)



# Thuật toán tìm kiếm phòng
# def find_rooms_by_guest_count(guest_count):
#     return Room.query.filter(
#         Room.capacity >= guest_count,
#         Room.active == True
#     ).all()

from flask import request, jsonify

@app.route('/booking_form/<int:room_id>', methods=['GET', 'POST'])
def booking_form(room_id):
    if request.method == 'POST':
        data = request.get_json()
        room_id = data.get('room_id')
        if room_id:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invalid room ID'}), 400

    room = dao.load_room_by_id(room_id)
    return render_template('booking_form.html', room=room)

from flask import request, redirect, url_for, flash
from datetime import datetime


@app.route('/submit_booking', methods=['POST'])
def submit_booking():
    try:
        # Lấy thông tin từ form
        username = current_user.username  # Lấy username của user đang đăng nhập
        room_name = request.form.get('room_name')
        checkin_date = datetime.strptime(request.form.get('checkin'), '%Y-%m-%d')
        checkout_date = datetime.strptime(request.form.get('checkout'), '%Y-%m-%d')

        # Đếm số lượng khách thực tế
        guest_count = 0
        guests_data = []
        for i in range(1, 4):
            guest_name = request.form.get(f'guest_{i}_name')
            guest_type = request.form.get(f'guest_{i}_type')
            guest_id = request.form.get(f'guest_{i}_id')
            guest_address = request.form.get(f'guest_{i}_address')

            if guest_name and guest_type and guest_id:
                guest_count += 1
                guests_data.append({
                    'name': guest_name,
                    'guest_type': guest_type,
                    'guest_id': guest_id,
                    'address': guest_address
                })

        # Lấy thông tin room và user
        room = Room.query.filter_by(name=room_name).first()
        user = User.query.filter_by(username=username).first()

        if not room:
            flash('Room not found', 'error')
            return redirect(url_for('index'))

        print(f"DEBUG - Room ID: {room.id}")
        print(f"DEBUG - User ID: {user.id}")
        print(f"DEBUG - Check-in: {checkin_date}")
        print(f"DEBUG - Check-out: {checkout_date}")
        print(f"DEBUG - Guest count: {guest_count}")

        # Tạo RoomDetail mới
        room_detail = RoomDetail(
            guest_count=guest_count,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            user_id=user.id,
            room_id=room.id,
            active=True,
            booking_status='PENDING'
        )

        # Lưu RoomDetail
        db.session.add(room_detail)
        db.session.flush()

        print(f"DEBUG - RoomDetail ID: {room_detail.id}")

        # Tạo và lưu thông tin Guest
        for guest_data in guests_data:
            guest = Guest(
                room_detail_id=room_detail.id,
                name=guest_data['name'],    
                guest_type=guest_data['guest_type'],
                guest_id=guest_data['guest_id'],
                address=guest_data['address']
            )
            db.session.add(guest)

        # Commit tất cả thay đổi
        db.session.commit()

        flash('Booking and guest information saved successfully!', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        db.session.rollback()
        print(f"DEBUG - Error: {str(e)}")
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('index'))


if __name__ == "__main__":
    with app.app_context():
        app.run(debug=True)

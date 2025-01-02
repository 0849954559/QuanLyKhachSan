from models import *
from hotelapp import app, db
import hashlib
from flask_login import current_user
from sqlalchemy import func
from datetime import datetime,timedelta


def find_available_rooms(room_type_id, guests, checkin_date, checkout_date):
    # Kiểm tra xem ngày checkin có cách ngày hiện tại không quá 28 ngày
    today = datetime.today().date()
    max_checkin_date = today + timedelta(days=28)

    if checkin_date > max_checkin_date:
        return []  # Trả về danh sách rỗng nếu ngày checkin vượt quá 28 ngày

    # Chỉ kiểm tra room type và capacity
    available_rooms = Room.query.filter(
        and_(
            Room.roomType_id == room_type_id,
            Room.capacity >= guests,
            Room.active == True
        )
    ).all()

    # Lọc thêm theo điều kiện checkin_date và checkout_date
    available_rooms = [room for room in available_rooms if room.check_availability(checkin_date, checkout_date)]

    return available_rooms

def load_roomtypes():
    # with open('data/roomtypes.json', encoding='utf-8') as f:
    #     return json.load(f)
    return RoomType.query.all()


def load_rooms(q=None, cate_id=None, page=None):
    # with open('data/rooms.json', encoding='utf-8') as f:
    #     rooms = json.load(f)
    #     if q:
    #         rooms = [p for p in rooms if p["name"].find(q)>=0]
    #     if cate_id:
    #         rooms = [p for p in rooms if p["roomType_id"].__eq__(int(cate_id))]
    #     return rooms
    query = Room.query

    if q:
        query = query.filter(Room.name.contains(q))

    if cate_id:
        query = query.filter(Room.roomType_id.__eq__(int(cate_id)))

    if page:
        page_size = app.config["PAGE_SIZE"]
        start = (int(page)-1)*page_size
        query = query.slice(start, start+page_size)

    return query.all()


def count_room():
    return Room.query.count()


def auth_user(username, password):
    if username and password:
        password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())
        return User.query.filter(User.username.__eq__(username.strip()),
                               User.password.__eq__(password)).first()
    return None


def load_room_by_id(id):
    # with open('data/rooms.json', encoding='utf-8') as f:
    #     rooms = json.load(f)
    #     for p in rooms:
    #         if p["id"] == id:
    #             return p
    return Room.query.get(id)


def add_user(name, username, password, avatar):
    password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())
    u = User(name=name, username=username, password=password, avatar=avatar)
    db.session.add(u)
    db.session.commit()


def get_user_by_id(user_id):
    return User.query.get(user_id)

def add_bill(user_id, room_id, roomdetails_id, quantity_day, total_amount):
    """Add a new bill to database"""
    if all([user_id, room_id, roomdetails_id, quantity_day, total_amount]):
        bill = Bill(
            user_id=user_id,
            room_id=room_id,
            roomdetails_id=roomdetails_id,
            quantity_day=quantity_day,
            total_amount=total_amount
        )
        db.session.add(bill)
        db.session.commit()
        return bill
    return None


def count_bills_by_room():
    """Count number of bills for each room"""
    return db.session.query(
        Room.id,
        Room.name,
        func.count(Bill.id)
    ).join(
        Bill,
        Bill.room_id.__eq__(Room.id),
        isouter=True
    ).group_by(Room.id).all()


def stats_revenue_by_room(kw=None):
    """Calculate total revenue for each room"""
    query = db.session.query(
        Room.id,
        Room.name,
        func.sum(Bill.total_amount)
    ).join(
        Bill,
        Bill.room_id.__eq__(Room.id),
        isouter=True
    )

    if kw:
        query = query.filter(Room.name.contains(kw))

    return query.group_by(Room.id).all()


def stats_revenue_by_period(year=datetime.now().year, period='month'):
    """Calculate revenue by time period (month/quarter/year)"""
    query = db.session.query(
        func.extract(period, Bill.created_date),
        func.sum(Bill.total_amount)
    ).filter(
        func.extract('year', Bill.created_date).__eq__(year)
    )

    return query.group_by(
        func.extract(period, Bill.created_date)
    ).all()



if __name__ == "__main__":
    print(load_rooms())





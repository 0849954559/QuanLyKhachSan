from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Enum, DateTime,CheckConstraint,text,and_,or_
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship
from hotelapp import app, db
from flask_login import UserMixin
from enum import Enum as RoleEnum
from datetime import datetime


class UserEnum(RoleEnum):
    USER = 1
    ADMIN = 2
    STAFF = 3




class User(db.Model, UserMixin):
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50))
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(50), nullable=False)
    active = Column(Boolean, default=True)
    avatar = Column(String(200), default="https://res.cloudinary.com/dy1unykph/image/upload/v1729842193/iPhone_15_Pro_Natural_1_ltf9vr.webp")
    role = Column(Enum(UserEnum), default=UserEnum.USER)


    def __str__(self):
        return self.name


class RoomType(db.Model):
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    rooms = relationship('Room', backref='roomType', lazy=True)


    def __str__(self):
        return self.name

class RoomStatus(Enum):
    AVAILABLE = 1      # Phòng trống, có thể đặt
    BOOKED = 2        # Phòng đã được đặt
    OCCUPIED = 3      # Phòng đang có khách
#    MAINTENANCE = 4   # Phòng đang bảo trì


class Room(db.Model):
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    capacity = Column(Integer, nullable=False)
    price = Column(Float, default=0)
    image = Column(String(200), default="https://res.cloudinary.com/dy1unykph/image/upload/v1729842193/iPhone_15_Pro_Natural_1_ltf9vr.webp")
    roomType_id = Column(Integer, ForeignKey(RoomType.id), nullable=False)
    status = Column(Integer, default= 1)
    active = Column(Boolean, default=True)  # True: phòng đang hoạt động, False: phòng ngừng hoạt động

    __table_args__ = (
        CheckConstraint('capacity >= 1 AND capacity <= 3', name='check_valid_capacity'),
        {'extend_existing': True}
    )

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        """Kiểm tra phòng có available để đặt không"""
        return self.active and self.status == 1

    def check_availability(self, check_in_date, check_out_date):
        """
        Kiểm tra phòng có available trong khoảng thời gian cụ thể không
        """
        if not self.active or self.status == 4:
            return False

        # Kiểm tra xem có booking nào overlap với thời gian này không
        overlapping_bookings = RoomDetail.query.filter(
            and_(
                RoomDetail.room_id == self.id,
                RoomDetail.active == True,
                or_(
                    and_(RoomDetail.checkin_date <= check_in_date,
                         RoomDetail.checkout_date > check_in_date),
                    and_(RoomDetail.checkin_date < check_out_date,
                         RoomDetail.checkout_date >= check_out_date),
                    and_(RoomDetail.checkin_date >= check_in_date,
                         RoomDetail.checkout_date <= check_out_date)
                )
            )
        ).count()

        return overlapping_bookings == 0

class RoomDetail(db.Model):
    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_count = Column(Integer, default=0)
    checkin_date = Column(DateTime, default=datetime.now(), nullable=False)
    checkout_date = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey(User.id))
    room_id = Column(Integer, ForeignKey(Room.id))
    active = Column(Boolean, default=True)  # True: đặt phòng có hiệu lực, False: đã hủy đặt phòng
    booking_status = Column(String(20), default='PENDING')  # PENDING, CONFIRMED, CHECKED_IN, CHECKED_OUT, CANCELLED

    user = relationship('User', backref='detail')  # Định nghĩa quan hệ với User
    room = relationship('Room', backref='detail')  # Định nghĩa quan hệ với Room
    guests = db.relationship('Guest', backref='room_detail', cascade="all, delete-orphan")


    __table_args__ = (
        CheckConstraint(
            text('DATEDIFF(checkout_date, checkin_date) <= 28'),
            name='check_valid_stay_duration'
        ),
        CheckConstraint(
            text('checkout_date > checkin_date'),
            name='check_valid_dates'
        ),
        {'extend_existing': True}
    )

    def confirm_booking(self):
        """Xác nhận đặt phòng"""
        if self.booking_status == 'PENDING':
            self.booking_status = 'CONFIRMED'
            self.room.status = 2
            return True
        return False

    def check_in(self):
        """Check-in khách"""
        if self.booking_status == 'CONFIRMED':
            self.booking_status = 'CHECKED_IN'
            self.room.status = 3
            return True
        return False

    def check_out(self):
        """Check-out khách"""
        if self.booking_status == 'CHECKED_IN':
            self.booking_status = 'CHECKED_OUT'
            self.room.status = 1
            return True
        return False

    def cancel_booking(self):
        """Hủy đặt phòng"""
        if self.booking_status in ['PENDING', 'CONFIRMED']:
            self.booking_status = 'CANCELLED'
            self.active = False
            self.room.status = 1
            return True
        return False


class Base(db.Model):
    __abstract__ = True
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now())


class Rules(Base):
    __tablename__ = 'rules'
    name = Column(String(50), nullable=False)  # Added name column
    details = relationship('RulesDetail', backref="rules", lazy=True)

class RulesDetail(Base):
    __tablename__ = 'rules_detail'
    content = Column(String(4000), nullable=True)
    surcharge = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    rules_id = Column(Integer, ForeignKey(Rules.id), nullable=False)
    room_id = Column(Integer, ForeignKey(Room.id), nullable=False)





class Guest(db.Model):
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_detail_id = Column(Integer, ForeignKey('room_detail.id'), nullable=False)  # Liên kết với RoomDetail
    name = Column(String(100), nullable=False)
    guest_type = Column(String(20), nullable=False)  # 'domestic' hoặc 'international'
    guest_id = Column(String(50), nullable=False)  # CMND hoặc ID
    address = Column(String(255), nullable=True)

class Bill(Base):
    __tablename__ = 'bill'
    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    roomdetails_id = Column(Integer, ForeignKey(RoomDetail.id), nullable=False)
    room_id = Column(Integer, ForeignKey(Room.id), nullable=False)
    quantity_day = Column(Integer, default=0)
    total_amount = Column(Float, default=0)
    payment_status = Column(Boolean, default=False)

    room_detail = relationship('RoomDetail', backref='bill', lazy=True)

    __table_args__ = (
        CheckConstraint('quantity_day >= 0', name='check_valid_quantity_day'),
        CheckConstraint('total_amount >= 0', name='check_valid_total_amount'),
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        c1 = RoomType(name="Single")
        c2 = RoomType(name="Double")
        c3 = RoomType(name="Deluxe")
        c4 = RoomType(name="Family")
        db.session.add_all([c1,c2,c3,c4])
        db.session.commit()
        import json
        with open('data/rooms.json', encoding='utf-8') as f:
            rooms = json.load(f)
            for p in rooms:
                prod = Room(**p)
                db.session.add(prod)

        import hashlib

        password = str(hashlib.md5("123123".encode('utf-8')).hexdigest())

        u = User(name="khoi", username="user", password=password)
        u2 = User(name="khoi1", username="admin", password=password, role=UserEnum.ADMIN)
        u3 = User(name="khoi2",username = "staff", password= password, role = UserEnum.STAFF)
        db.session.add_all([u,u2,u3])

        r1 = Rules(name="Room")
        r2 = Rules(name="Guest")
        r3 = Rules(name="Facilities")
        r4 = Rules(name="Staff")
        r5 = Rules(name="Admin")

        db.session.add_all([r1,r2,r3,r4,r5])


        with open('data/ruledetails.json', encoding='utf-8') as f:
            ruledetails = json.load(f)
            for p in ruledetails:
                rule = RulesDetail(**p)
                db.session.add(rule)
        db.session.commit()

        r1 = RoomDetail(
            id=1,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=101,
            active=True
        )
        r2 = RoomDetail(
            id=2,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=102,
            active=True
        )
        r3 = RoomDetail(
            id=3,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=201,
            active=True
        )
        r4 = RoomDetail(
            id=4,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=202,
            active=True
        )
        r5 = RoomDetail(
            id=5,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=203,
            active=True
        )
        r6 = RoomDetail(
            id=6,
            checkin_date=datetime(2024, 12, 25, 14, 0),
            checkout_date=datetime(2024, 12, 30, 11, 0),
            user_id=1,
            room_id=301,
            active=True
        )
        r7 = RoomDetail(
            id=7,
            checkin_date=datetime(2024, 12, 21, 14, 0),
            checkout_date=datetime(2024, 12, 23, 11, 0),
            user_id=1,
            room_id=301,
            active=True
        )

        # Thêm tất cả các bản ghi vào database
        db.session.add_all([r1, r2, r3, r4, r5, r6, r7])
        db.session.commit()

        # Sử dụng r1 làm room_detail
        guest1 = Guest(
            room_detail_id=r1.id,  # Sử dụng r1.id
            name="Nguyen Van A",
            guest_type="domestic",
            guest_id="123456789",
            address="123 Tran Phu, Da Nang"
        )
        
        guest2 = Guest(
            room_detail_id=r1.id,  # Sử dụng r1.id
            name="John Doe",
            guest_type="international",
            guest_id="987654321",
            address="45 Fifth Avenue, New York, USA"
        )
        
        # Thêm khách vào session và commit
        db.session.add(guest1)
        db.session.add(guest2)
        db.session.commit()

        billdel = [
            Bill(user_id=1, roomdetails_id=1, room_id=101, quantity_day=5, total_amount=1500000,
                 payment_status=True),
            Bill(user_id=1, roomdetails_id=2, room_id=102, quantity_day=5, total_amount=875000,
                 payment_status=True),
            Bill(user_id=1, roomdetails_id=3, room_id=201, quantity_day=5, total_amount=1300000,
                 payment_status=True),
            Bill(user_id=1, roomdetails_id=6, room_id=301, quantity_day=5, total_amount=1100000,
                 payment_status=True),
            Bill(user_id=1, roomdetails_id=5, room_id=203, quantity_day=5, total_amount=1100000,
                 payment_status=True),
        ]
        db.session.bulk_save_objects(billdel)
        db.session.commit()
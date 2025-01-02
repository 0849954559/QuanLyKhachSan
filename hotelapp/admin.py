import calendar
from datetime import datetime
from ensurepip import bootstrap

from flask_admin import Admin, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from sqlalchemy import func
from unicodedata import category

from hotelapp import app, db , dao
from models import RoomType, Room, UserEnum, User, RoomDetail, Bill, Rules, RulesDetail, RoomStatus, Guest
from flask_login import current_user, logout_user
from flask import redirect, request, flash
from flask_admin import BaseView
from markupsafe import Markup
from flask import redirect, url_for
from functools import wraps
from flask import abort



# Base View Classes for Authentication
class AdminRequiredMixin:
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == UserEnum.ADMIN

    def inaccessible_callback(self, name, **kwargs):
        flash('Vui lòng đăng nhập với tài khoản Admin', 'error')
        return redirect('login')


class StaffRequiredMixin:
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == UserEnum.STAFF

    def inaccessible_callback(self, name, **kwargs):
        flash('Vui lòng đăng nhập với tài khoản Staff', 'error')
        return redirect('login')


# Admin Views
class AdminModelView(AdminRequiredMixin, ModelView):
    pass


class MyRoomTypeView(AdminModelView):
    column_list = ["name", "rooms"]


# class MyRoomView(AdminModelView):
#     column_list = ["name", "roomType_id", "image", "capacity", "price"]
#     column_searchable_list = ["id", "name"]
#     column_filters = ["id", "name"]
#     can_export = True
#
#     column_formatters = {
#         "image": lambda view, context, model, name: Markup(
#             f'<img src="{model.image}" style="width: 50px; height: 50px; border-radius: 50%;">'
#         ),
#         "price": lambda view, context, model, name: f"{model.price:,.0f}".replace(",", ".") + " VNĐ/Đêm"
#     }


class MyRoomView(AdminModelView):
    column_list = ["name", "roomType_id", "image", "capacity", "price", "status", "active"]
    column_searchable_list = ["id", "name"]
    column_filters = ["id", "name", "status", "active"]
    can_export = True

    column_labels = {
        'name': 'Tên phòng',
        'roomType_id': 'Loại phòng',
        'image': 'Hình ảnh',
        'capacity': 'Sức chứa',
        'price': 'Giá phòng',
        'status': 'Trạng thái',
        'active': 'Đang hoạt động'
    }

    def _get_room_status_name(self, status):
        status_names = {
            1: "AVAILABLE",    # Phòng trống
            2: "OCCUPIED",     # Đang sử dụng
            3: "RESERVED"      # Đã đặt trước
        }
        return status_names.get(status, "UNKNOWN")

    def _get_status_badge(self, status):
        status_badges = {
            1: "success",      # Phòng trống - xanh lá
            2: "warning",      # Đang sử dụng - vàng
            3: "danger"        # Đã đặt trước - đỏ
        }
        return status_badges.get(status, "secondary")

    column_formatters = {
        "image": lambda view, context, model, name: Markup(
            f'<img src="{model.image}" style="width: 50px; height: 50px; border-radius: 50%;">'
        ),
        "price": lambda view, context, model, name: f"{model.price:,.0f}".replace(",", ".") + " VNĐ/Đêm",
        "status": lambda view, context, model, name: Markup(
            f'<span class="badge badge-{view._get_status_badge(model.status)}">'
            f'{view._get_room_status_name(model.status)}</span>'
        ),
        "active": lambda view, context, model, name: Markup(
            f'<span class="badge badge-{"success" if model.active else "danger"}">'
            f'{"Hợp lệ" if model.active else "Không hợp lệ"}</span>'
        )
    }

class UserView(AdminModelView):
    column_list = ["id", "name", "username", "password", "active", "avatar", "role"]
    form_columns = ["name", "username", "password", "active", "avatar", "role"]
    column_searchable_list = ["name", "username", "role"]
    column_filters = ["role"]

    column_formatters = {
        "avatar": lambda view, context, model, name: Markup(
            f'<img src="{model.avatar}" style="width: 50px; height: 50px; border-radius: 50%;">'
        )
    }


class AdminBaseView(AdminRequiredMixin, BaseView):
    pass


class StatsProfitView(AdminBaseView):
    @expose('/')
    def index(self):
        # Lấy năm được chọn từ query parameter, mặc định là năm hiện tại
        selected_year = request.args.get('year', datetime.now().year, type=int)

        # Lấy danh sách các năm có dữ liệu để tạo dropdown
        years = db.session.query(
            func.extract('year', Bill.created_date)
        ).distinct().all()
        years = [int(year[0]) for year in years]

        # Thống kê theo phòng
        revenue_by_room = db.session.query(
            Room.id,
            Room.name,
            func.count(Bill.id),
            func.sum(Bill.quantity_day),
            func.sum(Bill.total_amount)
        ).join(Bill).group_by(Room.id).all()

        # Thống kê theo thời gian (tháng)
        revenue_by_period = db.session.query(
            func.extract('month', Bill.created_date),
            func.count(Bill.id),
            func.sum(Bill.total_amount)
        ).filter(
            func.extract('year', Bill.created_date) == selected_year
        ).group_by(
            func.extract('month', Bill.created_date)
        ).all()

        # Thống kê hóa đơn chưa thanh toán
        unpaid_bills = db.session.query(
            Room.id,
            Room.name,
            Bill.created_date,
            Bill.quantity_day,
            Bill.total_amount
        ).join(Room).filter(
            Bill.payment_status == False
        ).all()

        return self.render('admin/stats.html',
                           revenue_by_room=revenue_by_room,
                           revenue_by_period=revenue_by_period,
                           unpaid_bills=unpaid_bills,
                           years=years,
                           selected_year=selected_year)



class StatsRoomUsageView(AdminBaseView):
    @expose('/')
    def index(self):
        # Lấy năm được chọn từ query parameter, mặc định là năm hiện tại
        selected_year = request.args.get('year', datetime.now().year, type=int)

        # Lấy danh sách các năm có dữ liệu
        years = db.session.query(
            func.extract('year', Bill.created_date)
        ).distinct().all()
        years = [int(year[0]) for year in years]

        # Thống kê mật độ sử dụng theo phòng
        usage_by_room = db.session.query(
            Room.id,
            Room.name,
            func.count(Bill.id).label('total_bookings'),
            func.sum(Bill.quantity_day).label('total_days_booked'),
            func.count(Bill.id).label('occupancy_count')
        ).join(Bill).group_by(Room.id).all()

        # Tính tổng số ngày trong năm và tỷ lệ sử dụng
        days_in_year = 365 if not calendar.isleap(selected_year) else 366
        usage_stats = []
        for room in usage_by_room:
            total_days_booked = room[3] if room[3] else 0
            occupancy_rate = (total_days_booked / days_in_year) * 100
            usage_stats.append({
                'room_id': room[0],
                'room_name': room[1],
                'total_bookings': room[2],
                'total_days_booked': total_days_booked,
                'occupancy_rate': round(occupancy_rate, 2)
            })

        # Thống kê mật độ sử dụng theo tháng
        usage_by_month = db.session.query(
            func.extract('month', Bill.created_date).label('month'),
            func.count(Bill.id).label('bookings'),
            func.sum(Bill.quantity_day).label('days_booked')
        ).filter(
            func.extract('year', Bill.created_date) == selected_year
        ).group_by(
            func.extract('month', Bill.created_date)
        ).all()

        # Tính toán phòng có mật độ sử dụng cao nhất và thấp nhất
        most_used_room = max(usage_stats, key=lambda x: x['occupancy_rate'])
        least_used_room = min(usage_stats, key=lambda x: x['occupancy_rate'])

        # Thống kê trạng thái phòng hiện tại
        current_room_status = db.session.query(
            Room.status,
            func.count(Room.id).label('count')
        ).group_by(Room.status).all()

        return self.render('admin/report.html',
                         usage_stats=usage_stats,
                         usage_by_month=usage_by_month,
                         most_used_room=most_used_room,
                         least_used_room=least_used_room,
                         current_room_status=current_room_status,
                         years=years,
                         selected_year=selected_year)


class RulesView(AdminModelView):
    column_list = ["id", "name", "created_date", "active"]
    can_export = True
    column_searchable_list = ["name"]  # Chỉ search theo name vì id là số
    column_filters = ["name", "created_date", "active"]
    column_labels = {
        'name': 'Người áp dụng',
        'created_date': 'Ngày tạo',
        'active': 'Hiệu lực'
    }


class RuleDetailView(AdminModelView):
    column_list = ["id","rules.name","content","surcharge","created_date"]
    can_export = True
    column_searchable_list = ["id","content"]
    column_filters = ["id","created_date","active"]
    column_labels = {
        'rules.name': 'Người áp dụng',
        'content': 'Nội dung',
        'surcharge': 'Phụ thu',
        'created_date':'Ngày Tạo'
    }
    column_formatters = {
        'created_date': lambda v, c, m, n: m.created_date.strftime('%d-%m-%Y'),
        'surcharge': lambda v, c, m, n: f"{m.surcharge:,.0f}".replace(",", ".") + " VNĐ/Người",
        'rules': lambda v, c, m, n: m.rules.name if m.rules else ''
    }

class AdminLogoutView(AdminBaseView):
    @expose('/')
    def index(self):
        logout_user()
        return redirect('/login')


class AdminIndexView(AdminRequiredMixin, AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')




# Staff Views
class StaffModelView(StaffRequiredMixin, ModelView):
    pass





class BookingView(StaffModelView):
    column_list = ['id', 'room.name', 'user.name', 'guest_count', 'checkin_date', 'checkout_date',
                   'booking_status', 'active']
    column_searchable_list = ['id', 'user.name', 'room.name']
    column_filters = ['checkin_date', 'checkout_date', 'booking_status', 'active']
    form_columns = ['booking_status', 'active']

    column_labels = {
        'room.name': 'Phòng',
        'user.name': 'Khách hàng',
        'guest_count': 'Số khách',
        'checkin_date': 'Ngày nhận phòng',
        'checkout_date': 'Ngày trả phòng',
        'booking_status': 'Trạng thái',
        'active': 'Hiệu lực'
    }

    column_formatters = {
        'checkin_date': lambda v, c, m, n: m.checkin_date.strftime('%d-%m-%Y'),
        'checkout_date': lambda v, c, m, n: m.checkout_date.strftime('%d-%m-%Y'),
        'booking_status': lambda v, c, m, n: Markup(
            f'<span class="badge badge-{get_booking_badge(m.booking_status)}">{m.booking_status}</span>'
        ),
        'active': lambda v, c, m, n: Markup(
            f'<span class="badge badge-{"success" if m.active else "danger"}">'
            f'{"Còn hiệu lực" if m.active else "Đã hủy"}</span>'
        )
    }

    def on_model_change(self, form, model, is_created):
        """Xử lý khi trạng thái booking thay đổi"""
        if not is_created:
            if model.booking_status == 'CONFIRMED':
                model.confirm_booking()
            elif model.booking_status == 'CHECKED_IN':
                model.check_in()
            elif model.booking_status == 'CHECKED_OUT':
                model.check_out()
            elif model.booking_status == 'CANCELLED':
                model.cancel_booking()

def get_booking_badge(status):
    status_badges = {
        'PENDING': 'warning',
        'CONFIRMED': 'info',
        'CHECKED_IN': 'primary',
        'CHECKED_OUT': 'success',
        'CANCELLED': 'danger'
    }
    return status_badges.get(status, 'secondary')


class BillView(AdminModelView):
    column_list = ['id', 'created_date', 'room_id', 'user_id', 'total_amount', 'payment_status']
    column_searchable_list = ['id', 'user_id']
    column_filters = ['created_date', 'payment_status']
    form_columns = ['payment_status']

    column_formatters = {
        'created_date': lambda v, c, m, n: m.created_date.strftime('%d-%m-%Y'),
        'total_amount': lambda v, c, m, n: f"{m.total_amount:,.0f}".replace(",", ".") + " VNĐ",
        'payment_status': lambda v, c, m, n: Markup(
            f'<span class="badge badge-{"success" if m.payment_status else "danger"}">'
            f'{"Đã thanh toán" if m.payment_status else "Chưa thanh toán"}</span>'
        )
    }


class StaffLogoutView(StaffRequiredMixin, BaseView):
    @expose('/')
    def index(self):
        logout_user()
        return redirect('/login')


class RoomDetailGuestView(StaffModelView):
    column_list = [
        'id', 'guest_names', 'checkin_date', 'checkout_date',
        'room.name', 'booking_status', 'active'
    ]

    # Tạo thuộc tính để lấy danh sách tên khách
    column_labels = {
        'guest_names': 'Tên khách',
        'checkin_date': 'Ngày nhận phòng',
        'checkout_date': 'Ngày trả phòng',
        'room.name': 'Phòng',
        'booking_status': 'Trạng thái',
        'active': 'Hiệu lực'
    }

    column_formatters = {
        'guest_names': lambda v, c, m, n: ', '.join(
            [guest.name for guest in m.guests]
        ),
        'checkin_date': lambda v, c, m, n: m.checkin_date.strftime('%d-%m-%Y %H:%M'),
        'checkout_date': lambda v, c, m, n: m.checkout_date.strftime('%d-%m-%Y %H:%M'),
        'booking_status': lambda v, c, m, n: Markup(
            f'<span class="badge badge-{get_booking_badge(m.booking_status)}">{m.booking_status}</span>'
        ),
        'active': lambda v, c, m, n: Markup(
            f'<span class="badge badge-{"success" if m.active else "danger"}">{"Hiệu lực" if m.active else "Đã hủy"}</span>'
        )
    }




# Create separate admin instances for Admin and Staff
admin = Admin(app=app, name="Admin Portal", template_mode="bootstrap4", index_view=AdminIndexView(), endpoint='admin')
staff = Admin(app=app, name="Staff Portal", template_mode="bootstrap4",url='/staff', endpoint='staff')

# Register Admin views
admin.add_view(MyRoomTypeView(RoomType, db.session, name="Loại Phòng",category="Phòng"))
admin.add_view(MyRoomView(Room, db.session, name="Phòng",category="Phòng"))
admin.add_view(UserView(User, db.session, name="Người dùng",category="Quản lý"))
admin.add_view(RulesView(Rules, db.session, name="Quy định", category="Quản lý"))
admin.add_view(BillView(Bill, db.session, name="Hóa đơn",category="Quản lý"))
admin.add_view(RuleDetailView(RulesDetail,db.session,name = "Chi tiết quy định",category = "Quản lý"))
admin.add_view(StatsProfitView(name="Doanh Thu", endpoint='stats',category="Báo cáo Thống kê"))
admin.add_view(StatsRoomUsageView(name="Mật độ", endpoint='report',category="Báo cáo Thống kê"))
admin.add_view(AdminLogoutView(name="Đăng xuất"))

# Register Staff views

staff.add_view(BookingView(RoomDetail, db.session, name="Quản lý phiếu đặt", endpoint="booking_view"))
staff.add_view(RoomDetailGuestView(RoomDetail, db.session, name="Quản lý phiếu thuê", endpoint="room_detail_view"))

staff.add_view(StaffLogoutView(name="Đăng xuất"))
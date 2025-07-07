from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Court, Booking, Blogs, Customer
from datetime import datetime, timedelta, time, date
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from .utils import process_booking, add_booking_to_sheet
from django.db.models import Sum, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDay, TruncWeek, TruncMonth


@login_required
def dashboard(request):
    # Get the selected period, default to 'daily'
    period = request.GET.get("period", "daily")
    today = timezone.now().date()

    # Determine the date range for filtering
    if period == "weekly":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "monthly":
        start_date = today.replace(day=1)
        # A reliable way to get the last day of the month
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
    else:  # daily
        start_date = today
        end_date = today

    # Filter bookings for the selected period
    period_bookings = Booking.objects.filter(booking_date__range=[start_date, end_date])

    # Calculate total stats for the cards
    total_bookings = period_bookings.count()
    total_revenue = period_bookings.aggregate(
        total=Coalesce(Sum("payment_amount"), Value(0, output_field=DecimalField()))
    )["total"]
    total_cash = period_bookings.filter(payment_method="CASH").aggregate(
        total=Coalesce(Sum("payment_amount"), Value(0, output_field=DecimalField()))
    )["total"]
    total_online = period_bookings.filter(payment_method="ONLINE").aggregate(
        total=Coalesce(Sum("payment_amount"), Value(0, output_field=DecimalField()))
    )["total"]

    # Aggregate booking data for the summary table, grouped by day
    booking_summary = (
        period_bookings.annotate(trunc_date=TruncDay("booking_date"))
        .values("trunc_date")
        .annotate(
            total_amount=Coalesce(Sum("payment_amount"), Value(0, output_field=DecimalField())),
            cash_amount=Coalesce(
                Sum(
                    Case(
                        When(payment_method="CASH", then="payment_amount"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                Value(0, output_field=DecimalField()),
            ),
            online_amount=Coalesce(
                Sum(
                    Case(
                        When(payment_method="ONLINE", then="payment_amount"),
                        default=Value(0),
                        output_field=DecimalField(),
                    )
                ),
                Value(0, output_field=DecimalField()),
            ),
        )
        .order_by("-trunc_date")
    )

    context = {
        "booking_summary": booking_summary,
        "selected_period": period,
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "total_cash": total_cash,
        "total_online": total_online,
    }

    return render(request, "core/dashboard.html", context)


@login_required
def ai_create_booking(request):
    if request.method == "POST":
        text = request.POST.get("text")
        try:
            booking_data = process_booking(text)
            print(booking_data)
            booking = Booking(
                user=request.user,
                booking_date=datetime.now().date(),
                start_time=booking_data.get("start_time"),
                end_time=booking_data.get("end_time"),
                note=f"Name: {booking_data.get('name', '')}, Phone: {booking_data.get('phone', '')}",
                ai_text=text,
                ai_text_json=booking_data,
                status="CONFIRMED",
                booking_price=booking_data.get("hourly_rate"),
                payment_amount=booking_data.get("hourly_rate") * booking_data.get("duration_in_hours")
            )
            booking.save()
            messages.success(request, "AI booking created successfully!")
            return redirect("booking_list")
        except Exception as e:
            messages.error(request, f"Error creating AI booking: {e}")
            return redirect("ai_create_booking")

    return render(request, "core/ai_create_booking.html")


def is_admin(user):
    return user.is_staff


def login_view(request):
    if request.user.is_authenticated:
        return redirect("booking_list")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            return redirect("booking_list")
        else:
            messages.error(request, "Invalid credentials or insufficient permissions.")

    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


# Modify your existing views to use this decorator
def admin_required(view_func):
    decorated_view = user_passes_test(is_admin, login_url="login")(view_func)
    return decorated_view


@login_required
def booking_list(request):
    # Get filter parameters from request
    pitch = request.GET.get("pitch")
    time_slot = request.GET.get("time")
    date = request.GET.get("date")

    # Start with base queryset - show all bookings by default
    booking_list = Booking.objects.select_related("court", "user").all()

    # Apply filters if they exist
    if pitch:
        booking_list = booking_list.filter(court_id=pitch)

    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            booking_list = booking_list.filter(booking_date=filter_date)
        except (ValueError, TypeError):
            pass  # Invalid date format, ignore the filter

    # Apply final ordering
    booking_list = booking_list.order_by("-booking_date", "-start_time")

    # Get all cricket nets for the filter dropdown
    courts = Court.objects.all()

    # Number of bookings per page
    per_page = 10
    paginator = Paginator(booking_list, per_page)
    page = request.GET.get("page", 1)

    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)

    context = {
        "bookings": bookings,
        "total_bookings": booking_list.count(),
        "courts": courts,
        "selected_pitch": pitch,
        "selected_date": date,
    }

    return render(request, "core/booking_list.html", context)


@admin_required
def create_booking(request):
    if request.method == "POST":
        try:
            court_id = request.POST.get("court")
            date_str = request.POST.get("date")
            start_time_str = request.POST.get("start_time")
            end_time_str = request.POST.get("end_time")
            
            # Convert string inputs to datetime objects
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
            booking_price = Decimal(request.POST.get("booking_price") or '0')
            bottle_amount = Decimal(request.POST.get("bottle_amount") or '0')
            total_amount = Decimal(request.POST.get("total_amount") or '0')
            advance_payment = Decimal(request.POST.get("advance_payment") or '0')
            advance_payment_method = request.POST.get("advance_payment_method")
            payment_method = request.POST.get("payment_method")
            payment_status = request.POST.get("payment_status") == "on"
            note = request.POST.get("note", "")

            court = Court.objects.get(id=court_id)

            # Check for existing bookings
            existing_booking = Booking.objects.filter(
                court=court,
                booking_date=date,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exists()

            if existing_booking:
                raise ValueError("This time slot is already booked.")


            if advance_payment > total_amount:
                raise ValueError("Advance payment cannot exceed total amount.")

            booking = Booking.objects.create(
                court=court,
                user=request.user,
                booking_date=date,
                start_time=start_time,
                end_time=end_time,
                booking_price=booking_price,
                bottle_amount=bottle_amount,
                payment_amount=total_amount,
                advance_payment=advance_payment,
                advance_payment_method=(
                    advance_payment_method if advance_payment > 0 else ""
                ),
                payment_method=payment_method,
                payment_status=payment_status,
                note=note,
                payment_date=timezone.now() if payment_status else None,
                status="CONFIRMED" if advance_payment > 0 or payment_status else "PENDING",
            )
            add_booking_to_sheet({
                'date_str': booking.booking_date.strftime('%Y-%m-%d'),
                'court': booking.court.name,
                "time_slot": f"{booking.start_time.strftime('%H:%M')} - {booking.end_time.strftime('%H:%M')}",
                "rate_per_hour": str(booking.booking_price),
                'total_amount': str(booking.payment_amount),
                'advance_payment': str(booking.advance_payment),
                'payment_method': booking.payment_method,
                'advance_payment_method': booking.advance_payment_method,
                'payment_status': 'Paid' if booking.payment_status else 'Pending',
                "advance": str(booking.advance_payment or 0),
                "bottle_amount": str(booking.bottle_amount or 0),
                "cash": str(booking.payment_amount - booking.advance_payment),
                'note': booking.note,
                'status': booking.status
            })
            messages.success(request, "Booking created successfully!")
            return redirect("booking_list")

        except ValueError as e:
            messages.error(request, str(e))
        # except Exception as e:
        #     messages.error(request, f"An error occurred: {str(e)}")
        return redirect("create_booking")

    courts = Court.objects.filter(is_active=True)
    return render(
        request,
        "core/create_booking.html",
        {"courts": courts},
    )


@admin_required
def delete_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.delete()
    messages.success(request, "Booking deleted successfully!")
    return redirect("booking_list")


@admin_required
def edit_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    courts = Court.objects.filter(is_active=True)
    customers = Customer.objects.all()

    if request.method == "POST":
        try:
            # Extract data from POST request
            booking.court_id = request.POST.get("court")
            date_str = request.POST.get("date")
            start_time_str = request.POST.get("start_time")
            end_time_str = request.POST.get("end_time")

            # Convert string inputs to datetime objects
            booking.booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            booking.start_time = datetime.strptime(start_time_str, "%H:%M").time()
            booking.end_time = datetime.strptime(end_time_str, "%H:%M").time()
            booking.booking_price = Decimal(request.POST.get("booking_price") or '0')
            booking.bottle_amount = Decimal(request.POST.get("bottle_amount") or '0')
            booking.payment_amount = Decimal(request.POST.get("total_amount") or '0')
            booking.advance_payment = Decimal(request.POST.get("advance_payment") or '0')
            booking.advance_payment_method = request.POST.get("advance_payment_method")
            booking.payment_method = request.POST.get("payment_method")
            booking.payment_status = request.POST.get("payment_status") == "on"
            booking.note = request.POST.get("note")


            # Validate advance payment
            if booking.advance_payment > booking.payment_amount:
                raise ValueError("Advance payment cannot exceed total amount.")

            # Update payment status and date
            if booking.payment_status:
                booking.payment_date = timezone.now()
            else:
                # If unchecked, reset payment status
                if (
                    booking.advance_payment < booking.payment_amount
                    or booking.advance_payment == 0
                ):
                    booking.payment_date = None

            # Update booking status
            if booking.advance_payment > 0:
                booking.status = "CONFIRMED"
            else:
                booking.status = "PENDING"

            booking.save()
            messages.success(request, "Booking updated successfully!")
            return redirect("booking_list")

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")

    return render(
        request, "core/edit_booking.html", {"booking": booking, "courts": courts, "customers": customers}
    )


def is_peak_hour(current_time):
    peak_start = time(17, 0)
    peak_end = time(22, 0)
    return peak_start <= current_time <= peak_end


def calculate_payment_amount(court, start_time, end_time):
    try:
        # Calculate duration considering midnight wrap
        if end_time < start_time:
            duration = timedelta(
                hours=24 - start_time.hour + end_time.hour,
                minutes=-start_time.minute + end_time.minute,
            )
        else:
            duration = timedelta(
                hours=end_time.hour - start_time.hour,
                minutes=end_time.minute - start_time.minute,
            )

        # Validate booking duration
        hours = duration.total_seconds() / 3600
        if hours < 1:
            raise ValueError("Minimum booking duration is 1 hour")
        if hours > 8:
            raise ValueError("Maximum booking duration is 8 hours")

        # Calculate peak and regular hours
        peak_minutes = 0
        # Convert to integer for range()
        total_minutes = int(duration.total_seconds() / 60)
        current_time = start_time

        for _ in range(total_minutes):
            if is_peak_hour(current_time):
                peak_minutes += 1
            current_time = (
                datetime.combine(date.today(), current_time) + timedelta(minutes=1)
            ).time()
            if current_time == time(0, 0):  # Handle midnight wraparound
                current_time = time(0, 1)

        # Convert to Decimal for final calculations
        peak_hours = Decimal(str(peak_minutes / 60))
        regular_hours = Decimal(str((total_minutes - peak_minutes) / 60))

        # Calculate total amount
        amount = (peak_hours * court.peak_hour_rate) + (
            regular_hours * court.hourly_rate
        )
        return Decimal(str(round(float(amount), 2)))

    except ValueError as e:
        raise e
    except Exception as e:
        print(e)
        raise ValueError(f"Error calculating payment amount: {str(e)}")


def get_blogs(request):
    blogs = Blogs.objects.filter(status="published")
    per_page = 9
    paginator = Paginator(booking_list, per_page)
    page = request.GET.get("page", 1)

    try:
        blogs = paginator.page(page)
    except PageNotAnInteger:
        blogs = paginator.page(1)
    except EmptyPage:
        blogs = paginator.page(paginator.num_pages)

    return JsonResponse({"blogs": blogs})


def get_blog_detail(request, blog_id):
    blog = get_object_or_404(Blogs, id=blog_id)
    return JsonResponse({"blog": blog})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CricketNet, Booking, Blogs
from datetime import datetime, timedelta, time, date
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse


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
    booking_list = Booking.objects.select_related("cricket_net", "user").all()

    # Apply filters if they exist
    if pitch:
        booking_list = booking_list.filter(cricket_net_id=pitch)

    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            booking_list = booking_list.filter(booking_date=filter_date)
        except (ValueError, TypeError):
            pass  # Invalid date format, ignore the filter

    # Apply final ordering
    booking_list = booking_list.order_by("-booking_date", "-start_time")

    # Get all cricket nets for the filter dropdown
    cricket_nets = CricketNet.objects.all()

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
        "cricket_nets": cricket_nets,
        "selected_pitch": pitch,
        "selected_date": date,
    }

    return render(request, "core/booking_list.html", context)


@admin_required
def create_booking(request):
    if request.method == "POST":
        try:
            net_id = request.POST.get("cricket_net")
            date = request.POST.get("date")
            start_time = request.POST.get("start_time")
            end_time = request.POST.get("end_time")
            payment_method = request.POST.get("payment_method")
            # Convert to Decimal instead of float for monetary calculations
            advance_payment = Decimal(request.POST.get("advance_payment", "0"))
            advance_payment_method = request.POST.get("advance_payment_method")
            note = request.POST.get("note", "")

            cricket_net = CricketNet.objects.get(id=net_id)

            # Check for existing bookings
            existing_booking = Booking.objects.filter(
                cricket_net=cricket_net,
                booking_date=date,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exists()

            if existing_booking:
                raise ValueError("This time slot is already booked.")

            payment_amount = calculate_payment_amount(cricket_net, start_time, end_time)

            # Convert payment_amount to Decimal if it isn't already
            if not isinstance(payment_amount, Decimal):
                payment_amount = Decimal(str(payment_amount))

            if advance_payment > payment_amount:
                raise ValueError("Advance payment cannot exceed total amount")

            booking = Booking.objects.create(
                cricket_net=cricket_net,
                user=request.user,
                booking_date=date,
                start_time=start_time,
                end_time=end_time,
                payment_method=payment_method,
                payment_amount=payment_amount,
                advance_payment=advance_payment,
                advance_payment_method=(
                    advance_payment_method if advance_payment > 0 else ""
                ),
                note=note,
                payment_status=advance_payment >= payment_amount,
                payment_date=(
                    timezone.now() if advance_payment >= payment_amount else None
                ),
                status="CONFIRMED" if advance_payment > 0 else "PENDING",
            )

            messages.success(request, "Booking created successfully!")
            return redirect("booking_list")

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
        return redirect("create_booking")

    cricket_nets = CricketNet.objects.filter(is_active=True)
    return render(
        request,
        "core/create_booking.html",
        {"cricket_nets": cricket_nets},
    )


@admin_required
def edit_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == "POST":
        try:
            payment_status = request.POST.get("payment_status") == "on"
            remaining_payment = Decimal(request.POST.get("remaining_payment", 0))
            payment_method = request.POST.get("payment_method")

            if remaining_payment > (booking.payment_amount - booking.advance_payment):
                raise ValueError("Payment amount exceeds remaining balance")

            if (
                payment_status
                and (booking.advance_payment + remaining_payment)
                < booking.payment_amount
            ):
                raise ValueError("Total payments do not match booking amount")

            booking.payment_status = payment_status

            # Status remains CONFIRMED if there was any advance payment
            if payment_status:
                booking.payment_date = timezone.now()
                if not booking.status == "CONFIRMED":
                    booking.status = "CONFIRMED"
                booking.payment_method = payment_method

            booking.save()

            messages.success(request, "Booking updated successfully!")
            return redirect("booking_list")

        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

    return render(request, "core/edit_booking.html", {"booking": booking})


def is_peak_hour(current_time):
    peak_start = time(17, 0)
    peak_end = time(22, 0)
    return peak_start <= current_time <= peak_end


def calculate_payment_amount(cricket_net, start_time, end_time):
    try:
        start_time = datetime.strptime(start_time, "%H:%M").time()
        end_time = datetime.strptime(end_time, "%H:%M").time()

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
        amount = (peak_hours * cricket_net.peak_hour_rate) + (
            regular_hours * cricket_net.hourly_rate
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

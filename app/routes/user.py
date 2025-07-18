from typing import Union, Tuple
from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    send_file,
    flash,
    jsonify,
    make_response,
    request,
    Response,
)
from werkzeug.wrappers import Response as WerkzeugResponse
from ..models import User, DiaryEntry, Goal, DailyStats, db
from ..forms import DeleteAccountForm, ChangeUsernameForm, ChangePasswordForm
from ..utils.progress_helpers import get_recent_entries
from werkzeug.security import check_password_hash
import io, csv, json

user_bp = Blueprint("user", __name__)


@user_bp.route("/profile")
def profile() -> Union[str, WerkzeugResponse]:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = db.session.get(User, session["user_id"])
    username_form = ChangeUsernameForm()
    password_form = ChangePasswordForm()

    # Check if user should see onboarding tour (new user with no entries)
    recent_entries = get_recent_entries(session["user_id"])
    is_new_user = len(recent_entries) == 0

    return render_template(
        "user/settings.html",
        user=user,
        username_form=username_form,
        password_form=password_form,
        is_new_user=is_new_user,
    )


@user_bp.route("/change-username", methods=["GET", "POST"])
def change_username() -> WerkzeugResponse:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = db.session.get(User, session["user_id"])
    form = ChangeUsernameForm()

    if form.validate_on_submit():
        try:
            # Update username
            user.user_name = form.new_username.data.strip()
            db.session.commit()

            flash("Username updated successfully!", "success")
            return redirect(url_for("user.profile"))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while updating username: {e}", "danger")
            return redirect(url_for("user.profile"))

    # If validation fails, redirect back to profile with errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, "danger")

    return redirect(url_for("user.profile"))


@user_bp.route("/change-password", methods=["GET", "POST"])
def change_password() -> WerkzeugResponse:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = db.session.get(User, session["user_id"])
    form = ChangePasswordForm()

    if form.validate_on_submit():
        # Verify current password
        if not user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("user.profile"))

        try:
            # Update password (the setter will handle hashing)
            user.password = form.new_password.data
            db.session.commit()

            flash("Password updated successfully!", "success")
            return redirect(url_for("user.profile"))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while updating password: {e}", "danger")
            return redirect(url_for("user.profile"))

    # If validation fails, redirect back to profile with errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, "danger")

    return redirect(url_for("user.profile"))


@user_bp.route("/download-data/json")
def download_data_json() -> Union[Response, WerkzeugResponse]:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    user_id = session["user_id"]
    user = User.query.get(user_id)
    diary_entries = DiaryEntry.query.filter_by(user_id=user_id).all()
    goals = Goal.query.filter_by(user_id=user_id).all()
    stats = DailyStats.query.filter_by(user_id=user_id).all()
    data = {
        "user": {"email": user.email, "user_name": user.user_name},
        "diary_entries": [
            {"date": e.entry_date.isoformat(), "content": e.content, "rating": e.rating}
            for e in diary_entries
        ],
        "goals": [
            {
                "title": g.title,
                "category": (
                    g.category.value
                    if hasattr(g.category, "value")
                    else str(g.category)
                ),
                "status": (
                    g.status.value if hasattr(g.status, "value") else str(g.status)
                ),
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in goals
        ],
        "stats": [
            {
                "date": s.date.isoformat(),
                "points": s.points,
                "current_streak": s.current_streak,
                "longest_streak": s.longest_streak,
            }
            for s in stats
        ],
    }
    response = make_response(json.dumps(data, indent=2))
    response.headers["Content-Disposition"] = "attachment; filename=user_data.json"
    response.mimetype = "application/json"
    return response


@user_bp.route("/download-data/csv")
def download_data_csv() -> Union[Response, WerkzeugResponse]:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))
    user_id = session["user_id"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Diary Entries"])
    writer.writerow(["Date", "Content", "Rating"])
    for e in DiaryEntry.query.filter_by(user_id=user_id).all():
        writer.writerow([e.entry_date, e.content, e.rating])
    writer.writerow([])
    writer.writerow(["Goals"])
    writer.writerow(["Title", "Category", "Status", "Created At"])
    for g in Goal.query.filter_by(user_id=user_id).all():
        writer.writerow([g.title, g.category, g.status, g.created_at])
    writer.writerow([])
    writer.writerow(["Stats"])
    writer.writerow(["Date", "Points", "Current Streak", "Longest Streak"])
    for s in DailyStats.query.filter_by(user_id=user_id).all():
        writer.writerow([s.date, s.points, s.current_streak, s.longest_streak])
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=user_data.csv"
    response.mimetype = "text/csv"
    return response


@user_bp.route("/delete-account", methods=["GET", "POST"])
def delete_account() -> Union[str, WerkzeugResponse]:
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    form = DeleteAccountForm()
    user = db.session.get(User, session["user_id"])

    if form.validate_on_submit():
        if user and user.check_password(form.password.data):
            try:
                # Delete associated data first
                DailyStats.query.filter_by(user_id=user.id).delete()
                Goal.query.filter_by(user_id=user.id).delete()
                DiaryEntry.query.filter_by(user_id=user.id).delete()

                # Delete the user
                db.session.delete(user)
                db.session.commit()

                session.clear()
                flash("Your account has been successfully deleted.", "success")
                return redirect(url_for("auth.login_page"))
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred during account deletion: {e}", "danger")
        else:
            flash("Incorrect password. Please try again.", "danger")

    # Check if user should see onboarding tour (new user with no entries)
    recent_entries = get_recent_entries(session["user_id"])
    is_new_user = len(recent_entries) == 0

    return render_template("user/delete_account_confirm.html", form=form, is_new_user=is_new_user)

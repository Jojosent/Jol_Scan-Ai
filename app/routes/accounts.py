"""Регистрация, профиль и проверка ролей по данным SQLite."""
import io
import re
from datetime import date
from functools import wraps

import click
from flask import Blueprint, abort, g, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, db

bp = Blueprint('accounts', __name__)
DUMMY_HASH = generate_password_hash('unused-placeholder')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')


@bp.before_app_request
def load_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if isinstance(user_id, int) else None


def require_admin():
    if not g.user or not g.user.is_admin:
        abort(403)


def require_user():
    if not g.user:
        abort(401, description='Жалғастыру үшін кіріңіз.')


def page_login(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not g.user:
            return redirect(url_for('accounts.login', next=request.path))
        return view(*args, **kwargs)
    return guarded


@bp.route('/register', methods=['GET', 'POST'])
@bp.route('/login', methods=['GET', 'POST'])
def login():
    registering = request.path == '/register'
    next_page = request.args.get('next', '')
    if next_page not in {'/admin', '/analyze', '/profile', '/jolserik'}:
        next_page = '/'
    error = ''
    email = ''
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not EMAIL.fullmatch(email) or len(email) > 254 or not 6 <= len(password) <= 128:
            error = 'Электрондық поштаны және кемінде 6 таңбалы құпиясөзді енгізіңіз.'
        else:
            user = db.session.scalar(db.select(User).where(User.email == email))
            if registering:
                if user:
                    error = 'Бұл электрондық пошта тіркелген.'
                else:
                    user = User(email=email, password_hash=generate_password_hash(password))
                    db.session.add(user)
                    try:
                        db.session.commit()
                    except IntegrityError:
                        db.session.rollback()
                        error = 'Бұл электрондық пошта тіркелген.'
            elif not check_password_hash(user.password_hash if user else DUMMY_HASH, password) or not user:
                error = 'Электрондық пошта немесе құпиясөз дұрыс емес.'
            if not error:
                session.clear()
                session['user_id'] = user.id
                return redirect('/profile' if registering else next_page)
    return render_template('account.html', page='register' if registering else 'login',
                           registering=registering, error=error, email=email)


@bp.post('/logout')
def logout():
    session.clear()
    return redirect('/')


@bp.route('/profile', methods=['GET', 'POST'])
@page_login
def profile():
    error = ''
    if request.method == 'POST':
        fields = {name: request.form.get(name, '').strip() for name in ('first_name', 'last_name', 'phone', 'bio')}
        try:
            if any(len(fields[name]) > limit for name, limit in [('first_name', 80), ('last_name', 80), ('phone', 32), ('bio', 500)]):
                raise ValueError()
            raw_birth = request.form.get('birth_date', '')
            birth_date = date.fromisoformat(raw_birth) if raw_birth else None
            if birth_date and birth_date > date.today():
                raise ValueError()
            avatar = request.files.get('avatar')
            avatar_bytes = None
            if avatar and avatar.filename:
                raw = avatar.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError()
                with Image.open(io.BytesIO(raw), formats=['JPEG', 'PNG', 'WEBP']) as image:
                    if image.width * image.height > 12_000_000:
                        raise ValueError()
                    image = ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((384, 384))
                    buffer = io.BytesIO()
                    image.save(buffer, 'JPEG', quality=85)
                    avatar_bytes = buffer.getvalue()
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
            error = 'Өрістерді тексеріңіз. Аватар JPG, PNG немесе WebP, ең көбі 2 МБ.'
        else:
            for name, value in fields.items():
                setattr(g.user, name, value)
            g.user.birth_date = birth_date
            if avatar_bytes:
                g.user.avatar = avatar_bytes
            elif request.form.get('remove_avatar'):
                g.user.avatar = None
            db.session.commit()
            return redirect(url_for('accounts.profile', updated=1))
    return render_template('profile.html', page='profile', error=error, updated=request.args.get('updated') == '1')


@bp.get('/profile/avatar')
def avatar():
    if not g.user or not g.user.avatar:
        abort(404)
    response = send_file(io.BytesIO(g.user.avatar), mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@bp.cli.command('create-admin')
@click.argument('email')
@click.password_option()
def create_admin(email, password):
    email = email.strip().lower()
    if not EMAIL.fullmatch(email) or len(email) > 254 or not 6 <= len(password) <= 128:
        raise click.ClickException('Invalid email or password length.')
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user and not user.is_admin:
        raise click.ClickException('Email is already associated with a regular account.')
    if not user:
        user = User(email=email)
        db.session.add(user)
    user.password_hash = generate_password_hash(password)
    user.is_admin = True
    db.session.commit()
    click.echo('Administrator saved.')

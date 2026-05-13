from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, WalletTransaction

wallet_bp = Blueprint('wallet', __name__)


@wallet_bp.route('/')
@login_required
def index():
    transactions = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(WalletTransaction.created_at.desc()).all()
    
    return render_template('wallet/index.html',
                         transactions=transactions,
                         balance=current_user.credits)


@wallet_bp.route('/history')
@login_required
def history():
    transactions = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(WalletTransaction.created_at.desc()).all()
    
    return render_template('wallet/history.html', transactions=transactions)


@wallet_bp.route('/add-credits', methods=['GET', 'POST'])
@login_required
def add_credits():
    if request.method == 'POST':
        amount = int(request.form.get('amount', 0))
        
        if amount <= 0:
            flash('Please enter a valid amount.', 'danger')
            return redirect(url_for('wallet.add_credits'))
        
        current_user.credits += amount
        
        transaction = WalletTransaction(
            user_id=current_user.id,
            amount=amount,
            transaction_type='deposit',
            description=f'Purchased {amount} credits'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        from app.utils.email import create_notification
        create_notification(
            current_user,
            "Credits Added! 💰",
            f"You've successfully added {amount} credits to your wallet.",
            'wallet',
            '/wallet'
        )
        
        flash(f'Successfully added {amount} credits!', 'success')
        return redirect(url_for('wallet.index'))
    
    credit_packages = [
        {'amount': 50, 'price': '$4.99', 'bonus': 0},
        {'amount': 100, 'price': '$8.99', 'bonus': 10},
        {'amount': 250, 'price': '$19.99', 'bonus': 50},
        {'amount': 500, 'price': '$34.99', 'bonus': 150},
        {'amount': 1000, 'price': '$59.99', 'bonus': 400}
    ]
    
    return render_template('wallet/add_credits.html', packages=credit_packages)


@wallet_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        amount = int(request.form.get('amount', 0))
        user_id = int(request.form.get('user_id'))
        
        if amount <= 0:
            flash('Please enter a valid amount.', 'danger')
            return redirect(url_for('wallet.transfer'))
        
        recipient = User.query.get(user_id)
        if not recipient:
            flash('User not found.', 'danger')
            return redirect(url_for('wallet.transfer'))
        
        if current_user.credits < amount:
            flash('Insufficient credits.', 'danger')
            return redirect(url_for('wallet.transfer'))
        
        current_user.credits -= amount
        recipient.credits += amount
        
        sender_transaction = WalletTransaction(
            user_id=current_user.id,
            amount=-amount,
            transaction_type='transfer_sent',
            description=f'Transferred {amount} credits to {recipient.username}',
            session_id=None
        )
        
        recipient_transaction = WalletTransaction(
            user_id=recipient.id,
            amount=amount,
            transaction_type='transfer_received',
            description=f'Received {amount} credits from {current_user.username}',
            session_id=None
        )
        
        db.session.add(sender_transaction)
        db.session.add(recipient_transaction)
        db.session.commit()
        
        flash(f'Successfully transferred {amount} credits to {recipient.username}!', 'success')
        return redirect(url_for('wallet.index'))
    
    return render_template('wallet/transfer.html')


@wallet_bp.route('/validate-credits/<int:amount>')
@login_required
def validate_credits(amount):
    if current_user.credits >= amount:
        return jsonify({'valid': True})
    return jsonify({'valid': False, 'message': 'Insufficient credits'})
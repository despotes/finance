import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, password_check

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # query username and cash of the user
    cash = db.execute("SELECT username, cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    # save username and cash in two variables
    username = cash[0]["username"]
    balance = cash[0]["cash"]

    # query transactions company name, symbol and number of shares hold by the users
    transactions = db.execute(
        "SELECT company, symbol, SUM(shares) FROM transactions WHERE UserId = :ui GROUP BY symbol HAVING SUM(shares) > 0", ui=session["user_id"])

    # look up for the new prices of the stocks holded
    new_stocks = [lookup(x['symbol']) for x in transactions]

    # inizialize the a list where to save the new prices multiplied for the number of shares
    total_prices = []

    for i in range(len(new_stocks)):
        total_prices.append(transactions[i]['SUM(shares)'] * new_stocks[i]["price"])

    # single stock prices in USD
    new_prices_usd = [usd(i["price"]) for i in new_stocks]

    total_prices_usd = [usd(j) for j in total_prices]

    total_sum = balance

    # evaluating the total balance of the users stock values plus his current cash
    for i in total_prices:
        total_sum += i

    return render_template("index.html", new_prices_usd=new_prices_usd, tr=transactions, tp_usd=total_prices_usd, new_st=new_stocks, total_sum=usd(total_sum),
                           balance=usd(balance), username=username)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure that the symbol of the stock was submitted
        if not request.form.get("symbol"):
            return apology("Must provide a name for the stock")

        # Ensure that the number of shares of the stock was submitted and it's a interger number
        elif not request.form.get("shares") or not request.form.get("shares").isalnum():
            return apology("Must provide a integer and positive number of shares")

        # try to transform the shares submitted in a int otherwise call for 400 error code
        try:
            int(request.form.get("shares"))

        except:
            return apology("Must provide an integer and positive number of shares")

        # look up for values of the stock and company name
        stock = lookup(request.form.get("symbol"))

        # ensure it was submitted a valid stock name
        if not stock:
            return apology("This stock doesn't exist")

        # query database for the cash owned by the users
        cash_row = db.execute("SELECT cash FROM users WHERE id = :ui", ui=session["user_id"])

        old_cash = cash_row[0]["cash"]

        # calculating the total stock price purchased by the users
        total_stock_price = stock["price"] * int(request.form.get("shares"))

        new_cash = old_cash - total_stock_price

        # ensure that the users has enough money to make the purchase
        if new_cash < 0:
            return apology("You don't have enough cash to buy")

        # save the transaction in the database
        transaction = db.execute("INSERT INTO transactions (company, symbol, shares, price, datetime, UserId)\
                                    VALUES(:c, :sy, :shares, :pr, datetime('now'), :ui)",
                                 c=stock["name"], sy=stock["symbol"], shares=int(request.form.get("shares")), pr=stock["price"], ui=session["user_id"])

        # update the users' cash in the database
        db.execute("UPDATE users SET cash = :c WHERE id = :ui",
                   c=new_cash, ui=session["user_id"])

        return render_template("bought.html",
                               st=stock, pr=usd(stock["price"]), shares=int(request.form.get("shares")),
                               nc=usd(new_cash), oc=usd(old_cash), t_st_pr=usd(total_stock_price))

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # query the database for the transactions
    transactions = db.execute(
        "SELECT company, symbol, shares, price, strftime('%d-%m-%Y %H:%M:%S', datetime) FROM transactions WHERE UserId = :ui ORDER BY id ASC", ui=session["user_id"])

    return render_template("history.html", tr=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Must provide a name for the stock")

        stock = lookup(request.form.get("symbol"))

        if not stock:
            return apology("This stock doesn't exist")

        return render_template("quoted.html", company=stock["name"], price=usd(stock["price"]), symbol=stock["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation password don't match")

        username = request.form.get("username")
        password = request.form.get("password")

        hashed = generate_password_hash(password)

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hashed)", username=username, hashed=hashed)

        if not result:
            return apology(f"{username} already used")

        ids = db.execute("SELECT id FROM users WHERE username = :username", username=username)

        session["user_id"] = ids[0]["id"]

        flash("You have registered successfully!")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """change password of the user"""

    if request.method == "POST":

        password = db.execute("SELECT hash FROM users WHERE id = :ui", ui=session["user_id"])

        old_password = password[0]["hash"]

        # Ensure the old password was submitted or it's equal to the old_password
        if not request.form.get("oldPassword"):
            return apology("Must provide the old password")

        # Ensure the old password was written correctly
        elif not check_password_hash(old_password, request.form.get("oldPassword")):
            return apology("You didn't write the old password correctly")

        # Ensure password was submitted
        elif not request.form.get("newPassword"):
            return apology("must provide password")

        # Ensure password and confirmation of the password match
        elif request.form.get("newPassword") != request.form.get("confirmation"):
            return apology("password and confirmation password don't match")

        new_password = request.form.get("newPassword")

        checked = password_check(new_password)

        # Checking if the password meets the requirements
        if not checked["password_ok"]:
            flash("Your password must be: 8 length, at least one lowercase and one uppercase letter, at least a digit and a special character like '?'")
            return apology("Your password doesn't meet the requirements")

        # generate password hash for the new password
        hashed = generate_password_hash(password)

        # update the user's password in the database
        result = db.execute("UPDATE users SET hash = :hs WHERE id = :ui", hs=hashed, ui=session["user_id"])

        flash("You have changed the password successfully!")
        return redirect(url_for('index'))

    else:
        return render_template("change-password.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # ensure the symbol was selected
        if not request.form.get("symbol"):
            return apology("Must provide a name for the stock")

        # ensure the number of shares was written
        elif not request.form.get("shares"):
            return apology("Must provide a number of shares")

        # query for the number of shares in the database with the symbol provided by the users
        stock_owned = db.execute("SELECT company, symbol, SUM(shares) FROM transactions WHERE UserId = :ui AND symbol =:symbol GROUP BY symbol", ui=session["user_id"],
                                 symbol=request.form.get("symbol"))

        # ensure user don't sell more shares than what he/she holds
        if int(request.form.get("shares")) > stock_owned[0]["SUM(shares)"]:
            return apology("You can't sell more shares than what you own")

        # look up for the current price of the share
        stock = lookup(request.form.get("symbol"))

        # ensures this stock still exist
        if not stock:
            return apology("This stock doesn't exist")

        # insert the transaction with a negative number
        transaction = db.execute("INSERT INTO transactions (company, symbol, shares, price, datetime, UserId)\
                                    VALUES(:c, :sy, :shares * -1, :pr, datetime('now'), :ui)",
                                 c=stock["name"], sy=stock["symbol"], shares=int(request.form.get("shares")), pr=stock["price"], ui=session["user_id"])

        # query the database to update the cash of the users after selling
        cash_row = db.execute("SELECT cash FROM users WHERE id = :ui", ui=session["user_id"])

        old_cash = cash_row[0]["cash"]

        total_stock_price = stock["price"] * int(request.form.get("shares"))

        new_cash = old_cash + total_stock_price

        db.execute("UPDATE users SET cash = cash + :pr * :sh WHERE id = :ui",
                   pr=stock["price"], sh=int(request.form.get("shares")), ui=session["user_id"])

        return render_template("sold.html",
                               st=stock, pr=usd(stock["price"]), shares=int(request.form.get("shares")),
                               nc=usd(new_cash), oc=usd(old_cash), t_st_pr=usd(total_stock_price))

    else:
        stocks_owned = db.execute(
            "SELECT company, symbol, SUM(shares) FROM transactions WHERE UserId = :ui GROUP BY symbol HAVING SUM(shares) > 0", ui=session["user_id"])

        return render_template("sell.html", st_o=stocks_owned)


@app.route("/updatecash", methods=["POST"])
@login_required
def updateCash():
    """Add new cash to the user portfolio"""

    if request.method == "POST":

        # ensure the users provide a quantity of cash to ass
        if not request.form.get("cash"):
            return apology("Sorry, you didn't specificy the cash quantity")

        # ensure the users provide a positive integer
        elif not request.form.get("cash").isalnum():
            return apology("Must provide a integer and positive quantity")

        # try to make the value in interger to make sure it's a valid number
        try:
            add_cash = int(request.form.get("cash"))

        except:
            return apology("Must provide a integer and positive quantity")

        # update the user's cash in the database
        db.execute("UPDATE users SET cash = cash + :ac WHERE id = :ui", ac=add_cash, ui=session["user_id"])

        flash(f"{usd(add_cash)} has been added to your account")

        return redirect(url_for("index"))


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
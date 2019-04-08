import sys
import math
import random
import copy


bse_sys_minprice = 1  # minimum price in the system, in cents/pennies
bse_sys_maxprice = 1000  # maximum price in the system, in cents/pennies
ticksize = 1  # minimum change in price, in cents/pennies


# a customer order which is given to a trader to complete
class Customer_Order:

    def __init__(self, time, tid, otype, price, qty):
        self.time = time      # the time the customer order was issued
        self.tid = tid        # the trader i.d. that this order is for
        self.otype = otype    # the order type of the customer order i.e. buy/sell
        self.price = price    # the limit price of the customer order
        self.qty = qty        # the quantity to buy/sell

    def __str__(self):
        return 'Customer Order [T=%5.2f %s %s P=%s Q=%s]' % (self.time, self.tid, self.otype, self.price, self.qty)


# an order created by a trader for the exchange
class Order:

    def __init__(self, time, tid, otype, qty, MES, params):
        self.time = time    # timestamp
        self.tid = tid      # trader i.d.
        self.otype = otype  # order type
        self.qty = qty      # quantity
        self.MES = MES      # minimum execution size
        self.oid = -1       # order i.d. (unique to each order on the Exchange)
        self.params = params 

    def __str__(self):
        if self.params[0] == "Normal":
            return 'Order [T=%5.2f %s %s Q=%s MES=%s OID=%d]' % (self.time, self.tid, self.otype, self.qty, self.MES, self.oid)
        elif self.params[0] == "BI":
            return 'BI [T=%5.2f %s %s Q=%s MES=%s OID=%d]' % (self.time, self.tid, self.otype, self.qty, self.MES, self.oid)
        elif self.params[0] == "QBO":
            return 'QBO [T=%5.2f %s %s Q=%s MES=%s OID=%d MID=%d]' % (self.time, self.tid, self.otype, self.qty, self.MES, self.oid, self.params[1])


# Orderbook_half is one side of the book: a list of bids or a list of asks, each sorted best-first
class Orderbook_half:

    def __init__(self, booktype):
        # booktype: bids or asks?
        self.booktype = booktype
        # a dictionary containing all traders and the number of orders they have in this order book
        self.traders = {}
        # list of orders received, sorted by size and then time
        self.orders = []
        # number of current orders
        self.num_orders = 0

    # find the position to insert the order into the order_book list such that the order_book list maintains
    # it's ordering of (size,time)
    def find_order_position(self, order):
        quantity = order.qty
        time = order.time
        position = 0
        for i in range(0,len(self.orders)):
            if quantity > self.orders[i].qty or (quantity == self.orders[i].qty and time < self.orders[i].time):
                break
            else:
                position += 1
        return position

    # add the order to the orders dictionary and to the order_book list
    def book_add(self, order):

        # if the trader with this tid already has an order in the order_book, then remove it
        # also set the write reponse to return
        if self.traders.get(order.tid) != None:
            self.book_del(order.tid)
            response = 'Overwrite'
        else:
            response = 'Addition'

        # Note. changing the order in the order_book list will also change the order in the orders dictonary
        
        # add the trader to the traders dictionary
        num_orders = self.num_orders
        self.traders[order.tid] = 1
        self.num_orders = len(self.traders)

        # add the order to order_book list
        position = self.find_order_position(order)
        self.orders.insert(position, order)

        # return whether this was an addition or an overwrite
        return response

    # delete the order by the trader with the given tid
    def book_del(self, tid):
        del(self.traders[tid])
        
        # calling pop changes the length of order_book so we have to break afterwards
        for i in range(0, len(self.orders)):
            if self.orders[i].tid == tid:
                self.orders.pop(i)
                break

        self.num_orders = len(self.orders)

    # print the current traders
    def print_traders(self):
        for key in self.traders:
            print("%s: %d" % (key, self.traders[key]))

    # print the current orders
    def print_orders(self):
        for order in self.orders:
            print(order)


# Orderbook for a single instrument: list of bids and list of asks
class Orderbook:

    def __init__(self):
        self.buy_side = Orderbook_half('Buy')
        self.sell_side = Orderbook_half('Sell')
        self.tape = []
        self.order_id = 0  #unique ID code for each quote accepted onto the book

    # add an order to the order book
    def add_order(self, order, verbose):
        # add a order to the exchange and update all internal records; return unique i.d.
        order.oid = self.order_id
        self.order_id = order.oid + 1
        # if verbose : print('QUID: order.quid=%d self.quote.id=%d' % (order.oid, self.order_id))
        if order.otype == 'Buy':
            response=self.buy_side.book_add(order)
        else:
            response=self.sell_side.book_add(order)
        return [order.oid, response]

    # delete an order from the order book
    def del_order(self, time, order, verbose):
        # delete a trader's order from the exchange, update all internal records
        if order.otype == 'Buy':
            self.buy_side.book_del(order.tid)
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)

        elif order.otype == 'Sell':
            self.sell_side.book_del(order.tid)
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)
        else:
            # neither bid nor ask?
            sys.exit('bad order type in del_quote()')


    # match two orders and perform the trade
    def find_order_match(self):

        # matching is buy-side friendly, so start with buys first
        for buy_order in self.buy_side.orders:
            for sell_order in self.sell_side.orders:
                # find two matching orders in the order_book list
                if buy_order.qty >= sell_order.MES and buy_order.MES <= sell_order.qty:
                    # work out how large the trade size will be
                    if buy_order.qty >= sell_order.qty:
                        trade_size = sell_order.qty
                    else:
                        trade_size = buy_order.qty
                    # return a dictionary containing the trade info
                    # Note. Here we are returning references to the orders, so changing the returned orders will
                    # change the orders in the order_book
                    return {"buy_order": buy_order, "sell_order": sell_order, "trade_size": trade_size}

        # if no match can be found, return None
        return None

    # given a buy order, a sell order and a trade size, perform the trade
    def perform_trade(self, traders, time, price, trade_info):

        # subtract the trade quantity from the orders' quantity
        trade_info["buy_order"].qty -= trade_info["trade_size"]
        trade_info["sell_order"].qty -= trade_info["trade_size"]

        # remove orders from the order_book
        self.buy_side.book_del(trade_info["buy_order"].tid)
        self.sell_side.book_del(trade_info["sell_order"].tid)

        # re-add the the residual
        if trade_info["buy_order"].qty > 0:
            # update the MES if necessary
            if trade_info["buy_order"].MES > trade_info["buy_order"].qty:
                trade_info["buy_order"].MES = trade_info["buy_order"].qty
            # add the order to the order_book list
            self.buy_side.book_add(trade_info["buy_order"])

        # re-add the residual
        if trade_info["sell_order"].qty > 0:
            # update the MES if necessary
            if trade_info["sell_order"].MES > trade_info["sell_order"].qty:
                trade_info["sell_order"].MES = trade_info["sell_order"].qty
            # add the order to the order_book list
            self.sell_side.book_add(trade_info["sell_order"])

        # create a record of the transaction to the tape
        trade = {   'type': 'Trade',
                    'time': time,
                    'price': price,
                    'quantity': trade_info["trade_size"],
                    'party1': trade_info["buy_order"].tid,
                    'party2': trade_info["sell_order"].tid}

        # the traders parameter may be set to none when we are just trying to test the uncross function
        if traders != None:
            # inform the traders of the trade
            traders[trade_info["buy_order"].tid].bookkeep(trade, False)
            traders[trade_info["sell_order"].tid].bookkeep(trade, False)

        # add a record to the tape
        self.tape.append(trade)

    # write the tape to an output file
    def tape_dump(self, fname, fmode, tmode):
        dumpfile = open(fname, fmode)
        # write the title for each column
        dumpfile.write('time, quantity, price\n')
        # write the information for each trade
        for tapeitem in self.tape:
            if tapeitem['type'] == 'Trade' :
                dumpfile.write('%s, %s, %s\n' % (tapeitem['time'], tapeitem['quantity'], tapeitem['price']))
        dumpfile.close()
        if tmode == 'wipe':
            self.tape = []

    # print the current orders in the orders dictionary
    def print_traders(self):
        print("Buy orders:")
        self.buy_side.print_traders()
        print("Sell orders:")
        self.sell_side.print_traders()

    # print the current orders in the order_book list
    def print_order_book(self):
        print("Order Book:")
        print("Buy side order book:")
        self.buy_side.print_orders()
        print("Sell side order book:")
        self.sell_side.print_orders()
        print("")

    def print_tape(self):
        print("Tape:")
        for trade in self.tape:
            print(trade)
        print("")


# Block Indication Book class for a single instrument. The class holds and performs operations with 
# received block indications
class Block_Indication_Book:

    # constructer function for the Block_Indication_Book class
    def __init__(self):
        # the buy side contains all of the block indications to buy
        self.buy_side = Orderbook_half('Buy')
        # the sell side contains all of the block indications to sell
        self.sell_side = Orderbook_half('Sell')
        # ID to be given to next block indication
        self.BI_id = 0
        # the reputational_scores dictionary contains the reputation score for each trader TID. The score will be
        # between 0 and 100
        self.reputational_scores = {}
        # the reputational score threshold (RST). All traders with a reputational score below this threshold
        # are no longer able to use the block discovery service
        self.RST = 20
        # The minimum indication value (MIV) is the quantity that a block indication must be greater
        # than in order to be accepted
        self.MIV = 20
        # A dictionary to contain the qualifying block orders that have been received
        self.qualifying_block_orders = {}
        # ID to be given to next qualifying block order
        self.QBO_id = 0
        # ID to be given to the matching of two block indications
        self.match_id = 0
        # The tape contains the history of block indications sent to the exchange
        self.tape = []

    
    # add block indication
    def add_block_indication(self, order, verbose):

        # if a new trader, then give it an initial reputational score
        if self.reputational_scores.get(order.tid) == None:
            self.reputational_scores[order.tid] = 50

        # the quantity of the order must be greater than the MIV
        if order.qty > self.MIV and self.reputational_scores.get(order.tid) > self.RST:

            # set the orders order id member variable
            order.oid = self.BI_id
            self.BI_id = order.oid + 1

            # add the block indication to the correct order book
            if order.otype == 'Buy':
                response=self.buy_side.book_add(order)
            else:
                response=self.sell_side.book_add(order)

            # return the order id and the response
            return [order.oid, response]

        # if the quantity of the order was not greater than the MIV then return a message
        return "Block Indication Rejected"

    # delete block indication
    def del_block_indication(self, time, order, verbose):
        # delete a trader's order from the exchange, update all internal records
        if order.otype == 'Buy':
            self.buy_side.book_del(order.tid)
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)

        elif order.otype == 'Sell':
            self.sell_side.book_del(order.tid)
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)
        else:
            # neither bid nor ask?
            sys.exit('bad order type in del_quote()')
    
    # add a qualifying block order. If matching qualifying block orders are recieved then they are
    # both returned. These are the final orders to be used in the exchange
    def add_qualifying_block_order(self, order, verbose):

        # give each qualifying block order its own unique id
        order.oid = self.QBO_id
        self.QBO_id += 1

        # get the match id for the orginally matched block indications
        match_id = order.params[1]

        # and the order to the qualifying_block_orders dictionary with the key as match_id
        if self.qualifying_block_orders.get(match_id) == None:
            if order.otype == 'Buy':
                self.qualifying_block_orders[match_id] = {"buy_side": order}
            elif order.otype == "Sell":
                self.qualifying_block_orders[match_id] = {"sell_side": order}
        else:
            if order.otype == 'Buy':
                self.qualifying_block_orders[match_id]["buy_side"] = order
            elif order.otype == 'Sell':
                self.qualifying_block_orders[match_id]["sell_side"] = order
        
        # if both QBOs have been received then return appropriate message
        if len(self.qualifying_block_orders.get(match_id)) == 2:
            QBOs = self.qualifying_block_orders.get(match_id)
            self.update_reputational_scores(QBOs)
            return "second QBO received"
        else:
            return "first QBO received"

    # attempt to find two matching block indications
    def find_matching_block_indications(self):
        # starting with the buy side first
        for buy_order in self.buy_side.orders:
            for sell_order in self.sell_side.orders:
                # check if the two block indications match
                if buy_order.qty >= sell_order.MES and buy_order.MES <= sell_order.qty:
                    # work out how large the trade size will be
                    if buy_order.qty >= sell_order.qty:
                        trade_size = sell_order.qty
                    else:
                        trade_size = buy_order.qty
                    # return a dictionary containing the match info
                    # Note. Here we are returning references to the orders, so changing the returned orders will
                    # change the orders in the order_book
                    response = {"buy_order": buy_order, "sell_order": sell_order, "trade_size": trade_size, "match_id": self.match_id}
                    self.match_id += 1
                    return response
        return None

    # return the reputational score for the given TID, if the TID is not known then return None
    def get_reputational_score(self, tid):
        return self.reputational_scores.get(tid)

    # calculate the reputational score of a trader for a single event
    def calculate_event_reputational_score(self, QBO, BI):

        # if the QBO's MES is greater than the BI's MES then it is not "marketable" so give score zero
        if QBO.MES > BI.MES:
            return 0

        # calculate the score for this event
        score = 100
        MES_percent_diff = 100 * (BI.MES - QBO.MES) / BI.MES
        quantity_percent_diff = 100 * (BI.qty - QBO.qty) / BI.qty
        score = 100 - MES_percent_diff - quantity_percent_diff
        if score > 100: score = 100
        if score < 50: score = 50

        return score

    # get the original block indication for the qualifying block order
    def get_QBOs_matching_BI(self, QBO):
        for order in self.buy_side.orders:
            if QBO.tid == order.tid:
                return order
        for order in self.sell_side.orders:
            if QBO.tid == order.tid:
                return order
        return None

    def update_reputational_scores(self, QBOs):

        # the QBO and BI for the buy side
        QBO_buy_side = QBOs["buy_side"]
        BI_buy_side = self.get_QBOs_matching_BI(QBO_buy_side)

        # the QBO and BI for the sell side
        QBO_sell_side = QBOs["sell_side"]
        BI_sell_side = self.get_QBOs_matching_BI(QBO_sell_side)

        # get the event reputation scores
        buy_side_event_score = self.calculate_event_reputational_score(QBO_buy_side, BI_buy_side)
        sell_side_event_score = self.calculate_event_reputational_score(QBO_sell_side, BI_sell_side)

        # update the traders' reputational score
        self.update_trader_reputational_score(QBO_buy_side.tid, buy_side_event_score)
        self.update_trader_reputational_score(QBO_sell_side.tid, sell_side_event_score)



    # update a traders reputational score given an event_score
    def update_trader_reputational_score(self, tid, event_score):
        self.reputational_scores[tid] = self.reputational_scores[tid] * 0.75 + event_score * 0.25


    # print the reputational score of all known traders
    def print_reputational_scores(self):
        print("Reputational scores:")
        for key in self.reputational_scores:
            print("%s : %d" % (key, self.reputational_scores[key]))
        print("")

    # print the current traders with block indications
    def print_traders(self):
        print("Buy orders:")
        self.buy_side.print_traders()
        print("Sell orders:")
        self.sell_side.print_traders()

    # print the current block indications
    def print_block_indications(self):
        print("Block Indications:")
        print("Buy side order book:")
        self.buy_side.print_orders()
        print("Sell side order book:")
        self.sell_side.print_orders()
        print("")

    # print all of the current qualifying block orders
    def print_qualifying_block_orders(self):
        print("Qualifying block orders:")
        for key in self.qualifying_block_orders.keys():
            print("Match id: %d" % key)
            if self.qualifying_block_orders[key]["buy_side"]:
                print(self.qualifying_block_orders[key]["buy_side"])
            if self.qualifying_block_orders[key]["sell_side"]:
                print(self.qualifying_block_orders[key]["sell_side"])
        print("")

# Exchange

class Exchange:

    # constructor method
    def __init__(self):
        self.order_book = Orderbook()
        self.block_indications = Block_Indication_Book()

    # add an order to the exchange
    def add_order(self, order, verbose):
        return self.order_book.add_order(order, verbose)
    
    def add_block_indication(self, BI, verbose):
        return self.block_indications.add_block_indication(BI, verbose)

    def add_qualifying_block_order(self, QBO, verbose):
        return self.block_indications.add_qualifying_block_order(QBO, verbose)


    # delete an order from the exchange
    def del_order(self, time, order, verbose):
        return self.order_book.del_order(time, order, verbose)

    # this function executes the uncross event, trades occur at the given time at the given price
    # keep making trades out of matching order until no more matches can be found
    def uncross(self, traders, time, price):

        # find a match between a buy order a sell order
        match_info = self.order_book.find_order_match()

        # keep on going until no more matches can be found
        while match_info != None:

            # execute the trade with the matched orders
            self.order_book.perform_trade(traders, time, 50.0, match_info)

            # find another match
            match_info = self.order_book.find_order_match()

    def del_block_indication(self, time, order, verbose):
        response = self.block_indications.del_block_indication(time, order, verbose)
        return response

    # write the order_book's tape to the output file
    def tape_dump(self, fname, fmode, tmode):
        self.order_book.tape_dump(fname, fmode, tmode)

    # get the reputational score of a tid from the block indication book
    def get_reputational_score(self, tid):
        return self.block_indications.get_reputational_score(tid)

    def get_QBOs_matching_BI(self, QBO):
        return self.block_indications.get_QBOs_matching_BI(QBO)

    # print the current orders in the orders dictionary
    def print_traders(self):
        self.order_book.print_traders()

    # print the current orders in the order_book list
    def print_order_book(self):
        self.order_book.print_order_book()

    def print_block_indication_traders(self):
        self.block_indications.print_block_indication_traders()

    def print_block_indications(self):
        self.block_indications.print_block_indications()

    def print_reputational_scores(self):
        self.block_indications.print_reputational_scores()

    def print_qualifying_block_orders(self):
        self.block_indications.print_qualifying_block_orders()

##################--Traders below here--#############


# Trader superclass
# all Traders have a trader id, bank balance, blotter, and list of orders to execute
class Trader:

    def __init__(self, ttype, tid, balance, time):
        self.ttype = ttype             # what type / strategy this trader is
        self.tid = tid                 # trader unique ID code
        self.balance = balance         # money in the bank
        self.blotter = []              # record of trades executed
        self.customer_order = None     # customer orders currently being worked (fixed at 1)
        self.n_quotes = 0              # number of quotes live on LOB
        self.willing = 1               # used in ZIP etc
        self.able = 1                  # used in ZIP etc
        self.birthtime = time          # used when calculating age of a trader/strategy
        self.profitpertime = 0         # profit per unit time
        self.n_trades = 0              # how many trades has this trader done?
        self.lastquote = None          # record of what its last quote was


    def __str__(self):
        return '[TID %s type %s balance %s blotter %s customer order %s n_trades %s profitpertime %s]' \
            % (self.tid, self.ttype, self.balance, self.blotter, self.customer_order, self.n_trades, self.profitpertime)


    def add_order(self, customer_order, verbose):
        # in this version, trader has at most one order,
        # if allow more than one, this needs to be self.orders.append(order)
        if self.n_quotes > 0 :
            # this trader has a live quote on the LOB, from a previous customer order
            # need response to signal cancellation/withdrawal of that quote
            response = 'LOB_Cancel'
        else:
            response = 'Proceed'
        self.customer_order = customer_order
        if verbose : print('add_order < response=%s' % response)
        return response


    def del_order(self, order):
        # this is lazy: assumes each trader has only one customer order with quantity=1, so deleting sole order
        # CHANGE TO DELETE THE HEAD OF THE LIST AND KEEP THE TAIL
        self.customer_order = None


    def bookkeep(self, trade, verbose):

        outstr=str(self.customer_order)

        self.blotter.append(trade)  # add trade record to trader's blotter
        # NB What follows is **LAZY** -- assumes all orders are quantity=1
        transactionprice = trade['price']
        if self.customer_order.otype == 'Buy':
            profit = (self.customer_order.price - transactionprice) * trade['quantity']
        else:
            profit = (transactionprice - self.customer_order.price) * trade['quantity']
        self.balance += profit
        self.n_trades += 1
        self.profitpertime = self.balance/(trade['time'] - self.birthtime)

        if verbose: print('%s profit=%d balance=%d profit/time=%d' % (outstr, profit, self.balance, self.profitpertime))


    # specify how trader responds to events in the market
    # this is a null action, expect it to be overloaded by specific algos
    def respond(self, time, lob, trade, verbose):
        return None

    # specify how trader mutates its parameter values
    # this is a null action, expect it to be overloaded by specific algos
    def mutate(self, time, lob, trade, verbose):
        return None


# Trader subclass Giveaway
# even dumber than a ZI-U: just give the deal away
# (but never makes a loss)
class Trader_Giveaway(Trader):

    def getorder(self, time):
        if self.customer_order == None:
            order = None
        elif self.customer_order.qty >= 20:
            MES = 20
            # return a block indication
            order = Order(time, self.tid, self.customer_order.otype, self.customer_order.qty, MES, ["BI"])
            return order
        else:
            MES = 2
            order = Order(time, self.tid, self.customer_order.otype, self.customer_order.qty, MES, ["Normal"])
            self.lastquote=order
            return order

    # the trader recieves an Order Submission Request (OSR), the trader needs to respond with a
    # Qualifying Block Order (QBO) in order to confirm their block indication
    def order_submission_request(self, time, match_id):
        MES = 20
        order = Order(time, self.tid, self.customer_order.otype, self.customer_order.qty, MES, ["QBO", match_id])
        return order



##########################---Below lies the experiment/test-rig---##################



# trade_stats()
# dump CSV statistics on exchange data and trader population to file for later analysis
# this makes no assumptions about the number of types of traders, or
# the number of traders of any one type -- allows either/both to change
# between successive calls, but that does make it inefficient as it has to
# re-analyse the entire set of traders on each call
def trade_stats(expid, traders, dumpfile, time):

        # calculate the total balance sum for each type of trader and the number of each type of trader
        trader_types = {}
        n_traders = len(traders)
        for t in traders:
                ttype = traders[t].ttype
                if ttype in trader_types.keys():
                        t_balance = trader_types[ttype]['balance_sum'] + traders[t].balance
                        n = trader_types[ttype]['n'] + 1
                else:
                        t_balance = traders[t].balance
                        n = 1
                trader_types[ttype] = {'n':n, 'balance_sum':t_balance}

        # write the title for each column
        dumpfile.write('trial, time,')
        for i in range(0, len(trader_types)):
            dumpfile.write('type, sum, n, avg\n')

        # write the trial number followed by the time
        dumpfile.write('%s, %06d, ' % (expid, time))
        # for each type of trader write: the type name, the total balance sum of all traders of that type,
        # the number of traders of that type, and then the average balance of each trader of that type
        for ttype in sorted(list(trader_types.keys())):
                n = trader_types[ttype]['n']
                s = trader_types[ttype]['balance_sum']
                dumpfile.write('%s, %d, %d, %f, ' % (ttype, s, n, s / float(n)))
        dumpfile.write('N, ')
        # write a new line
        dumpfile.write('\n');



# create a bunch of traders from traders_spec
# returns tuple (n_buyers, n_sellers)
# optionally shuffles the pack of buyers and the pack of sellers
def populate_market(traders_spec, traders, shuffle, verbose):

        # given a trader type and a name, create the trader
        def trader_type(robottype, name):
                if robottype == 'GVWY':
                        return Trader_Giveaway('GVWY', name, 0.00, 0)
                elif robottype == 'ZIC':
                        return Trader_ZIC('ZIC', name, 0.00, 0)
                elif robottype == 'SHVR':
                        return Trader_Shaver('SHVR', name, 0.00, 0)
                elif robottype == 'SNPR':
                        return Trader_Sniper('SNPR', name, 0.00, 0)
                elif robottype == 'ZIP':
                        return Trader_ZIP('ZIP', name, 0.00, 0)
                else:
                        sys.exit('FATAL: don\'t know robot type %s\n' % robottype)


        def shuffle_traders(ttype_char, n, traders):
                for swap in range(n):
                        t1 = (n - 1) - swap
                        t2 = random.randint(0, t1)
                        t1name = '%c%02d' % (ttype_char, t1)
                        t2name = '%c%02d' % (ttype_char, t2)
                        traders[t1name].tid = t2name
                        traders[t2name].tid = t1name
                        temp = traders[t1name]
                        traders[t1name] = traders[t2name]
                        traders[t2name] = temp

        # create the buyers from the specification and add them to the traders dictionary
        n_buyers = 0
        for bs in traders_spec['buyers']:
                ttype = bs[0]
                for b in range(bs[1]):
                        tname = 'B%02d' % n_buyers  # buyer i.d. string
                        traders[tname] = trader_type(ttype, tname)
                        n_buyers = n_buyers + 1

        if n_buyers < 1:
                sys.exit('FATAL: no buyers specified\n')

        if shuffle: shuffle_traders('B', n_buyers, traders)

        # create the sellers from the specification and add them to the traders dictionary
        n_sellers = 0
        for ss in traders_spec['sellers']:
                ttype = ss[0]
                for s in range(ss[1]):
                        tname = 'S%02d' % n_sellers  # buyer i.d. string
                        traders[tname] = trader_type(ttype, tname)
                        n_sellers = n_sellers + 1

        if n_sellers < 1:
                sys.exit('FATAL: no sellers specified\n')

        if shuffle: shuffle_traders('S', n_sellers, traders)

        # print the information about each trader
        if verbose :
                for t in range(n_buyers):
                        bname = 'B%02d' % t
                        print(traders[bname])
                for t in range(n_sellers):
                        bname = 'S%02d' % t
                        print(traders[bname])


        return {'n_buyers':n_buyers, 'n_sellers':n_sellers}



# customer_orders(): allocate orders to traders
# parameter "os" is order schedule
# os['timemode'] is either 'periodic', 'drip-fixed', 'drip-jitter', or 'drip-poisson'
# os['interval'] is number of seconds for a full cycle of replenishment
# drip-poisson sequences will be normalised to ensure time of last replenishment <= interval
# parameter "pending" is the list of future orders (if this is empty, generates a new one from os)
# revised "pending" is the returned value
#
# also returns a list of "cancellations": trader-ids for those traders who are now working a new order and hence
# need to kill quotes already on LOB from working previous order
#
#
# if a supply or demand schedule mode is "random" and more than one range is supplied in ranges[],
# then each time a price is generated one of the ranges is chosen equiprobably and
# the price is then generated uniform-randomly from that range
#
# if len(range)==2, interpreted as min and max values on the schedule, specifying linear supply/demand curve
# if len(range)==3, first two vals are min & max, third value should be a function that generates a dynamic price offset
#                   -- the offset value applies equally to the min & max, so gradient of linear sup/dem curve doesn't vary
# if len(range)==4, the third value is function that gives dynamic offset for schedule min,
#                   and fourth is a function giving dynamic offset for schedule max, so gradient of sup/dem linear curve can vary
#
# the interface on this is a bit of a mess... could do with refactoring


def customer_orders(time, last_update, traders, trader_stats, os, pending, verbose):


        def sysmin_check(price):
                if price < bse_sys_minprice:
                        print('WARNING: price < bse_sys_min -- clipped')
                        price = bse_sys_minprice
                return price


        def sysmax_check(price):
                if price > bse_sys_maxprice:
                        print('WARNING: price > bse_sys_max -- clipped')
                        price = bse_sys_maxprice
                return price

        
        # return the order price for trader i out of n by using the selected mode
        def getorderprice(i, sched, n, mode, issuetime):
                # does the first schedule range include optional dynamic offset function(s)?
                if len(sched[0]) > 2:
                        offsetfn = sched[0][2]
                        if callable(offsetfn):
                                # same offset for min and max
                                offset_min = offsetfn(issuetime)
                                offset_max = offset_min
                        else:
                                sys.exit('FAIL: 3rd argument of sched in getorderprice() not callable')
                        if len(sched[0]) > 3:
                                # if second offset function is specfied, that applies only to the max value
                                offsetfn = sched[0][3]
                                if callable(offsetfn):
                                        # this function applies to max
                                        offset_max = offsetfn(issuetime)
                                else:
                                        sys.exit('FAIL: 4th argument of sched in getorderprice() not callable')
                else:
                        offset_min = 0.0
                        offset_max = 0.0

                pmin = sysmin_check(offset_min + min(sched[0][0], sched[0][1]))
                pmax = sysmax_check(offset_max + max(sched[0][0], sched[0][1]))
                prange = pmax - pmin
                stepsize = prange / (n - 1)
                halfstep = round(stepsize / 2.0)

                if mode == 'fixed':
                        orderprice = pmin + int(i * stepsize) 
                elif mode == 'jittered':
                        orderprice = pmin + int(i * stepsize) + random.randint(-halfstep, halfstep)
                elif mode == 'random':
                        if len(sched) > 1:
                                # more than one schedule: choose one equiprobably
                                s = random.randint(0, len(sched) - 1)
                                pmin = sysmin_check(min(sched[s][0], sched[s][1]))
                                pmax = sysmax_check(max(sched[s][0], sched[s][1]))
                        orderprice = random.randint(pmin, pmax)
                else:
                        sys.exit('FAIL: Unknown mode in schedule')
                orderprice = sysmin_check(sysmax_check(orderprice))
                return orderprice


        # return a dictionary containing the issue times of orders according to the selected issuing mode
        def getissuetimes(n_traders, mode, interval, shuffle, fittointerval):
                interval = float(interval)
                if n_traders < 1:
                        sys.exit('FAIL: n_traders < 1 in getissuetime()')
                elif n_traders == 1:
                        tstep = interval
                else:
                        tstep = interval / (n_traders - 1)
                arrtime = 0
                issuetimes = []
                for t in range(n_traders):
                        if mode == 'periodic':
                                arrtime = interval
                        elif mode == 'drip-fixed':
                                arrtime = t * tstep
                        elif mode == 'drip-jitter':
                                arrtime = t * tstep + tstep * random.random()
                        elif mode == 'drip-poisson':
                                # poisson requires a bit of extra work
                                interarrivaltime = random.expovariate(n_traders / interval)
                                arrtime += interarrivaltime
                        else:
                                sys.exit('FAIL: unknown time-mode in getissuetimes()')
                        issuetimes.append(arrtime) 
                        
                # at this point, arrtime is the last arrival time
                if fittointerval and ((arrtime > interval) or (arrtime < interval)):
                        # generated sum of interarrival times longer than the interval
                        # squish them back so that last arrival falls at t=interval
                        for t in range(n_traders):
                                issuetimes[t] = interval * (issuetimes[t] / arrtime)
                # optionally randomly shuffle the times
                if shuffle:
                        for t in range(n_traders):
                                i = (n_traders - 1) - t
                                j = random.randint(0, i)
                                tmp = issuetimes[i]
                                issuetimes[i] = issuetimes[j]
                                issuetimes[j] = tmp
                return issuetimes
        

        # return a tuple containing the current ranges and stepmode      
        def getschedmode(time, os):
                got_one = False
                for sched in os:
                        if (sched['from'] <= time) and (time < sched['to']) :
                                # within the timezone for this schedule
                                schedrange = sched['ranges']
                                mode = sched['stepmode']
                                got_one = True
                                exit  # jump out the loop -- so the first matching timezone has priority over any others
                if not got_one:
                        sys.exit('Fail: time=%5.2f not within any timezone in os=%s' % (time, os))
                return (schedrange, mode)
        

        n_buyers = trader_stats['n_buyers']
        n_sellers = trader_stats['n_sellers']

        shuffle_times = True

        cancellations = []

        # if there are no pending orders
        if len(pending) < 1:
                # list of pending (to-be-issued) customer orders is empty, so generate a new one
                new_pending = []

                # add the demand side (buyers) customer orders to the list of pending orders
                issuetimes = getissuetimes(n_buyers, os['timemode'], os['interval'], shuffle_times, True)
                ordertype = 'Buy'
                (sched, mode) = getschedmode(time, os['dem'])             
                for t in range(n_buyers):
                        issuetime = time + issuetimes[t]
                        tname = 'B%02d' % t
                        orderprice = getorderprice(t, sched, n_buyers, mode, issuetime)
                        # generating a random order quantity
                        quantity = random.randint(1,10)
                        customer_order = Customer_Order(issuetime, tname, ordertype, orderprice, quantity)
                        new_pending.append(customer_order)
                        
                # add the supply side (sellers) customer orders to the list of pending orders
                issuetimes = getissuetimes(n_sellers, os['timemode'], os['interval'], shuffle_times, True)
                ordertype = 'Sell'
                (sched, mode) = getschedmode(time, os['sup'])
                for t in range(n_sellers):
                        issuetime = time + issuetimes[t]
                        tname = 'S%02d' % t
                        orderprice = getorderprice(t, sched, n_sellers, mode, issuetime)
                        # generating a random order quantity
                        quantity = random.randint(1,10)
                        customer_order = Customer_Order(issuetime, tname, ordertype, orderprice, quantity)
                        new_pending.append(customer_order)
        # if there are some pending orders
        else:
                # there are pending future orders: issue any whose timestamp is in the past
                new_pending = []
                for order in pending:
                        if order.time < time:
                                # this order should have been issued by now
                                # issue it to the trader
                                tname = order.tid
                                response = traders[tname].add_order(order, verbose)
                                if verbose: print('Customer order: %s %s' % (response, order) )
                                # if issuing the order causes the trader to cancel their current order then add
                                # the traders name to the cancellations list
                                if response == 'LOB_Cancel' :
                                    cancellations.append(tname)
                                    if verbose: print('Cancellations: %s' % (cancellations))
                                # and then don't add it to new_pending (i.e., delete it)
                        else:
                                # this order stays on the pending list
                                new_pending.append(order)
        return [new_pending, cancellations]

# one session in the market
def market_session(sess_id, starttime, endtime, trader_spec, order_schedule, dumpfile, dump_each_trade):

        # variables which dictate what information is printed to the output
        verbose = False
        traders_verbose = False
        orders_verbose = False
        lob_verbose = False
        process_verbose = False
        respond_verbose = False
        bookkeep_verbose = False


        # initialise the exchange
        exchange = Exchange()


        # create a bunch of traders
        traders = {}
        trader_stats = populate_market(trader_spec, traders, True, traders_verbose)


        # timestep set so that can process all traders in one second
        # NB minimum interarrival time of customer orders may be much less than this!! 
        timestep = 1.0 / float(trader_stats['n_buyers'] + trader_stats['n_sellers'])
        
        duration = float(endtime - starttime)

        last_update = -1.0

        time = starttime

        # this list contains all the pending customer orders that are yet to happen
        pending_cust_orders = []

        print('\n%s;  ' % (sess_id))

        while time < endtime:

                # how much time left, as a percentage?
                time_left = (endtime - time) / duration

                if verbose: print('%s; t=%08.2f (%4.1f/100) ' % (sess_id, time, time_left*100))

                trade = None

                # update the pending customer orders list by generating new orders if none remain and issue 
                # any customer orders that were scheduled in the past. Note these are customer orders being
                # issued to traders, quotes will not be put onto the exchange yet
                [pending_cust_orders, kills] = customer_orders(time, last_update, traders, trader_stats,
                                                 order_schedule, pending_cust_orders, orders_verbose)

                # if any newly-issued customer orders mean quotes on the LOB need to be cancelled, kill them
                if len(kills) > 0 :
                        if verbose : print('Kills: %s' % (kills))
                        for kill in kills :
                                if verbose : print('lastquote=%s' % traders[kill].lastquote)
                                if traders[kill].lastquote != None :
                                        if verbose : print('Killing order %s' % (str(traders[kill].lastquote)))
                                        exchange.del_order(time, traders[kill].lastquote, verbose)


                # get a limit-order quote (or None) from a randomly chosen trader
                tid = list(traders.keys())[random.randint(0, len(traders) - 1)]
                order = traders[tid].getorder(time, time_left)

                if verbose: print('Trader Quote: %s' % (order))

                # if the randomly selected trader gives us a quote, then add it to the exchange
                if order != None:
                        # send order to exchange
                        traders[tid].n_quotes = 1
                        result = exchange.add_order(order, process_verbose)

                exchange.print_order_book()

                time = time + timestep


        # end of an experiment -- dump the tape
        exchange.tape_dump('transactions.csv', 'w', 'keep')


        # write trade_stats for this experiment NB end-of-session summary only
        trade_stats(sess_id, traders, dumpfile, time)




def experiment1():

    start_time = 0.0
    end_time = 20.0
    duration = end_time - start_time

    range1 = (75, 125)
    supply_schedule = [ {'from':start_time, 'to':end_time, 'ranges':[range1], 'stepmode':'fixed'}
                      ]

    range1 = (75, 125)
    demand_schedule = [ {'from':start_time, 'to':end_time, 'ranges':[range1], 'stepmode':'fixed'}
                      ]

    order_sched = {'sup':supply_schedule, 'dem':demand_schedule,
                   'interval':10, 'timemode':'drip-fixed'}

    buyers_spec = [('GVWY',5)]
    sellers_spec = buyers_spec
    traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}

    n_trials = 1
    tdump=open('avg_balance.csv','w')
    trial = 1
    if n_trials > 1:
            dump_all = False
    else:
            dump_all = True
            
    while (trial<(n_trials+1)):
            trial_id = 'trial%04d' % trial
            market_session(trial_id, start_time, end_time, traders_spec, order_sched, tdump, dump_all)
            tdump.flush()
            trial = trial + 1
    tdump.close()

    sys.exit('Done Now')


def test1():

    # create the trader specs
    buyers_spec = [('GVWY',5)]
    sellers_spec = buyers_spec
    traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}

    # initialise the exchange
    exchange = Exchange()

    # create a bunch of traders
    traders = {}
    trader_stats = populate_market(traders_spec, traders, True, False)

    # create some customer orders
    customer_orders = []
    customer_orders.append(Customer_Order(25.0, 'B00', 'Buy', 100, 5,))
    customer_orders.append(Customer_Order(35.0, 'B01', 'Buy', 100, 10))
    customer_orders.append(Customer_Order(55.0, 'B02', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(75.0, 'B03', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(65.0, 'B04', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(45.0, 'S00', 'Sell', 0, 11))
    customer_orders.append(Customer_Order(55.0, 'S01', 'Sell', 0, 4))
    customer_orders.append(Customer_Order(65.0, 'S02', 'Sell', 0, 6))
    customer_orders.append(Customer_Order(55.0, 'S03', 'Sell', 0, 6))

    for customer_order in customer_orders:
        traders[customer_order.tid].add_order(customer_order, False)

    print(traders)

    for tid in traders:
        order = traders[tid].getorder(20.0)
        if order != None:
            exchange.add_order(order, False)

    # print the order book before the uncross event
    print("\nStarting order book")
    exchange.print_traders()
    exchange.print_order_book()

    # invoke an uncross event
    exchange.uncross(traders, 5.0, 25.0)

    # print the order book after the uncross event
    print("\nEnding order book")
    exchange.print_order_book()
    exchange.print_traders()

    # print the tape at the end of the uncross event
    print("\ntape")
    print(exchange.order_book.tape)

    # end of an experiment -- dump the tape
    exchange.tape_dump('dark_transactions.csv', 'w', 'keep')
    # write trade_stats for this experiment NB end-of-session summary only
    dumpfile = open('dark_avg_balance.csv','w')
    trade_stats(1, traders, dumpfile, 200)

def test2():

    # initialise the exchange
    exchange = Exchange()

    # create the trader specs
    buyers_spec = [('GVWY',6)]
    sellers_spec = buyers_spec
    traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}

    # create a bunch of traders
    traders = {}
    trader_stats = populate_market(traders_spec, traders, True, False)

    # create some customer orders
    customer_orders = []
    customer_orders.append(Customer_Order(25.0, 'B00', 'Buy', 100, 5,))
    customer_orders.append(Customer_Order(35.0, 'B01', 'Buy', 100, 10))
    customer_orders.append(Customer_Order(55.0, 'B02', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(75.0, 'B03', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(65.0, 'B04', 'Buy', 100, 3))
    customer_orders.append(Customer_Order(45.0, 'B05', 'Buy', 100, 25))
    customer_orders.append(Customer_Order(45.0, 'S00', 'Sell', 0, 11))
    customer_orders.append(Customer_Order(55.0, 'S01', 'Sell', 0, 4))
    customer_orders.append(Customer_Order(65.0, 'S02', 'Sell', 0, 6))
    customer_orders.append(Customer_Order(55.0, 'S03', 'Sell', 0, 6))
    customer_orders.append(Customer_Order(75.0, 'S04', 'Sell', 0, 31))

    # assign customer orders to traders
    for customer_order in customer_orders:
        traders[customer_order.tid].add_order(customer_order, False)


    # add each traders order to the exchange
    for tid in traders:
        order = traders[tid].getorder(20.0)
        if order != None:
            print(exchange.add_order(order, False))

    exchange.print_order_book()
    exchange.print_block_indications()
    exchange.print_reputational_scores()

def test3():

    # initialise the exchange
    exchange = Exchange()

    # create some example orders
    orders = []
    orders.append(Order(25.0, 'B00', 'Buy', 5, 3, ["Normal"]))
    orders.append(Order(35.0, 'B01', 'Buy', 10, 6, ["Normal"]))
    orders.append(Order(55.0, 'B02', 'Buy', 3, 1, ["Normal"]))
    orders.append(Order(75.0, 'B03', 'Buy', 3, 2, ["Normal"]))
    orders.append(Order(45.0, 'S00', 'Sell', 11, 6, ["Normal"]))
    orders.append(Order(55.0, 'S01', 'Sell', 4, 2, ["Normal"]))
    orders.append(Order(65.0, 'S02', 'Sell', 6, 3, ["Normal"]))
    orders.append(Order(55.0, 'S03', 'Sell', 6, 4, ["Normal"]))

    block_indications = []
    block_indications.append(Order(65.0, 'B04', 'Buy', 50, 29, ["BI"]))
    block_indications.append(Order(85.0, 'S04', 'Sell', 30, 23, ["BI"]))

    # add the orders to the exchange
    for order in orders:

        # add the order to the exchange
        exchange.add_order(order, False)

    
    for block_indication in block_indications:

        # add the block indication to the exchange
        exchange.add_block_indication(block_indication, False)

        # check if there is a match between any two block indications
        match = exchange.block_indications.find_matching_block_indications()

        if match != None:

            buy_side_tid = match["buy_order"].tid
            sell_side_tid = match["sell_order"].tid
            match_id = match["match_id"]

            # create QBOs for matched BIs
            buy_side_qbo = copy.deepcopy(match["buy_order"])
            buy_side_qbo.params = ["QBO", match_id]
            sell_side_qbo = copy.deepcopy(match["sell_order"])
            sell_side_qbo.params = ["QBO", match_id]

            # add the QBOs to the exchange
            exchange.add_qualifying_block_order(buy_side_qbo, False)
            print(exchange.add_qualifying_block_order(sell_side_qbo, False))

            print(isinstance(buy_side_qbo, Order))
            

    exchange.print_block_indications()
    exchange.print_qualifying_block_orders()
    exchange.print_reputational_scores()

    # end of an experiment -- dump the tape
    exchange.tape_dump('dark_transactions.csv', 'w', 'keep')

# the main function is called if BSE.py is run as the main program
if __name__ == "__main__":
    test3()
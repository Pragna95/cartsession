
import { useEffect, useState } from "react";

const API = "http://localhost:8000/api";

async function req(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts
  });

  const d = await r.json();

  if (!r.ok) {
    throw Error(d.detail || "Request failed");
  }

  return d;
}

export default function App() {
  const [sid, setSid] = useState(
    sessionStorage.getItem("cart_session")
  );

  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({
    items: [],
    total: 0,
    item_count: 0
  });

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [error, setError] = useState("");

  // Checkout states
  const [showCheckout, setShowCheckout] = useState(false);
  const [checkoutOrder, setCheckoutOrder] = useState(null);
  const [orderPlaced, setOrderPlaced] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  async function init() {
    let id = sessionStorage.getItem("cart_session");

    if (id) {
      try {
        await req(`/sessions/${id}`);
      } catch {
        id = null;
      }
    }

    if (!id) {
      const s = await req("/sessions", {
        method: "POST"
      });

      id = s.session_id;
      sessionStorage.setItem("cart_session", id);
    }

    setSid(id);

    setCart(await req(`/cart/${id}`));
    setProducts(await req("/products"));
  }

  useEffect(() => {
    init().catch(e => setError(e.message));
  }, []);

  async function refresh() {
    const updatedCart = await req(`/cart/${sid}`);
    setCart(updatedCart);
  }

  async function action(path, opts) {
    try {
      setError("");

      const d = await req(path, opts);
      setCart(d);
    } catch (e) {
      setError(e.message);
    }
  }

  async function find(v) {
    setSearch(v);

    try {
      setProducts(
        await req(`/products?q=${encodeURIComponent(v)}`)
      );
    } catch (e) {
      setError(e.message);
    }
  }

  // Open checkout
  function openCheckout() {
    setCheckoutOrder({
      items: cart.items.map(item => ({
        ...item,
        product: { ...item.product }
      })),
      total: cart.total
    });

    setOrderPlaced(false);
    setShowCheckout(true);
  }

  // Confirm demo order
  async function confirmOrder() {
    try {
      setError("");
      setCheckoutLoading(true);

      const updatedCart = await req(`/cart/${sid}`, {
        method: "DELETE"
      });

      setCart(updatedCart);
      setOrderPlaced(true);

    } catch (e) {
      setError(e.message);
    } finally {
      setCheckoutLoading(false);
    }
  }

  const cats = [
    "All",
    ...new Set(products.map(p => p.category))
  ];

  const shown =
    category === "All"
      ? products
      : products.filter(p => p.category === category);

  return (
    <div className="page">

      {/* HEADER */}
      <header>
        <a className="logo">
          cart<span>ly.</span>
        </a>

        <input
          className="search"
          placeholder="Search products..."
          value={search}
          onChange={e => find(e.target.value)}
        />

        <span className="session">
          ● Session active
        </span>

        <a href="#cart" className="cartlink">
          🛒 Cart ({cart.item_count})
        </a>
      </header>

      {/* HERO */}
      <section className="hero">
        <div>
          <small>THE EVERYDAY STORE</small>

          <h1>
            Find your next
            <br />
            <i>favourite thing.</i>
          </h1>

          <p>
            Discover everyday essentials, explore our collection
            and add your favourites to the cart.
          </p>

          <a href="#products" className="cta">
            Explore products →
          </a>
        </div>

        <div className="hero-art">
          ✦
          <br />
          SHOP
          <br />
          <b>HAPPY ☺</b>
        </div>
      </section>

      {/* ERROR MESSAGE */}
      {error && (
        <div className="error">
          {error}
        </div>
      )}

      <div className="layout">

        {/* PRODUCTS SECTION */}
        <main id="products">

          <div className="heading">
            <div>
              <small>CURATED FOR YOU</small>
              <h2>Popular products</h2>
            </div>

            <span>{shown.length} items</span>
          </div>

          {/* CATEGORY FILTER */}
          <nav>
            {cats.map(c => (
              <button
                className={c === category ? "selected" : ""}
                onClick={() => setCategory(c)}
                key={c}
              >
                {c}
              </button>
            ))}
          </nav>

          {/* PRODUCT LIST */}
          <div className="products">
            {shown.map(p => (
              <article className="product" key={p.id}>

                <img src={p.image} alt={p.name} />

                <div className="pbody">
                  <small>{p.category}</small>

                  <h3>{p.name}</h3>

                  <p>{p.description}</p>

                  <div className="pfoot">
                    <b>
                      ₹{p.price.toLocaleString("en-IN")}
                    </b>

                    <button
                      onClick={() =>
                        action(`/cart/${sid}/items`, {
                          method: "POST",
                          body: JSON.stringify({
                            product_id: p.id,
                            quantity: 1
                          })
                        })
                      }
                    >
                      ＋ Add
                    </button>
                  </div>

                  <small>{p.stock} available</small>
                </div>

              </article>
            ))}
          </div>
        </main>

        {/* SHOPPING CART */}
        <aside id="cart">

          <small>YOUR SELECTION</small>

          <h2>
            Shopping cart <span>{cart.item_count}</span>
          </h2>

          <div className="sid">
            ◷ Guest session · {sid?.slice(0, 8)}…
          </div>

          {cart.items.length === 0 ? (

            <div className="empty">
              <div>🛒</div>
              <b>Your cart is waiting</b>
              <p>
                Add something you love and it will appear here.
              </p>
            </div>

          ) : (

            cart.items.map(it => (
              <div className="cartitem" key={it.product.id}>

                <img src={it.product.image} alt={it.product.name} />

                <div className="cartdesc">
                  <b>{it.product.name}</b>

                  <strong>
                    ₹{it.product.price.toLocaleString("en-IN")}
                  </strong>

                  <div className="qty">

                    <button
                      onClick={() =>
                        it.quantity === 1
                          ? action(
                              `/cart/${sid}/items/${it.product.id}`,
                              { method: "DELETE" }
                            )
                          : action(
                              `/cart/${sid}/items/${it.product.id}`,
                              {
                                method: "PATCH",
                                body: JSON.stringify({
                                  quantity: it.quantity - 1
                                })
                              }
                            )
                      }
                    >
                      −
                    </button>

                    {it.quantity}

                    <button
                      onClick={() =>
                        action(
                          `/cart/${sid}/items/${it.product.id}`,
                          {
                            method: "PATCH",
                            body: JSON.stringify({
                              quantity: it.quantity + 1
                            })
                          }
                        )
                      }
                    >
                      ＋
                    </button>

                  </div>
                </div>

                <button
                  className="remove"
                  onClick={() =>
                    action(
                      `/cart/${sid}/items/${it.product.id}`,
                      { method: "DELETE" }
                    )
                  }
                >
                  ×
                </button>

              </div>
            ))
          )}

          {/* CART TOTAL */}
          <div className="totals">

            <p>
              Subtotal
              <b>₹{cart.total.toLocaleString("en-IN")}</b>
            </p>

            <p>
              Delivery
              <b className="free">FREE</b>
            </p>

            <h3>
              Total
              <b>₹{cart.total.toLocaleString("en-IN")}</b>
            </h3>

            <button
              className="checkout"
              onClick={openCheckout}
              disabled={!cart.items.length}
            >
              Continue to checkout →
            </button>

            <button
              className="clear"
              onClick={() =>
                action(`/cart/${sid}`, {
                  method: "DELETE"
                })
              }
              disabled={!cart.items.length}
            >
              Clear cart
            </button>

          </div>

          <small className="saved">
            ↻ Cart saved for this active session.
          </small>

        </aside>
      </div>

      {/* CHECKOUT MODAL */}
      {showCheckout && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px"
          }}
        >
          <div
            style={{
              background: "white",
              color: "#222",
              padding: "30px",
              borderRadius: "16px",
              width: "100%",
              maxWidth: "450px",
              maxHeight: "80vh",
              overflowY: "auto",
              boxShadow: "0 10px 40px rgba(0,0,0,0.2)"
            }}
          >

            {orderPlaced ? (

              <>
                <h2>🎉 Order Confirmed!</h2>

                <p>
                  Your demo order has been placed successfully.
                </p>

                <p>
                  Thank you for shopping with Cartly!
                </p>

                <button
                  className="checkout"
                  onClick={() => {
                    setShowCheckout(false);
                    setCheckoutOrder(null);
                  }}
                >
                  Continue Shopping
                </button>
              </>

            ) : (

              <>
                <h2>Order Summary</h2>

                {checkoutOrder?.items.map(item => (
                  <div
                    key={item.product.id}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: "12px",
                      padding: "10px 0",
                      borderBottom: "1px solid #eee"
                    }}
                  >
                    <span>
                      {item.product.name} × {item.quantity}
                    </span>

                    <b>
                      ₹{(
                        item.product.price * item.quantity
                      ).toLocaleString("en-IN")}
                    </b>
                  </div>
                ))}

                <h3>
                  Total: ₹
                  {checkoutOrder?.total.toLocaleString("en-IN")}
                </h3>

                <p
                  style={{
                    background: "#f5f5f5",
                    padding: "12px",
                    borderRadius: "8px",
                    fontSize: "13px"
                  }}
                >
                  Demo checkout – no real payment will be processed.
                </p>

                <button
                  className="checkout"
                  onClick={confirmOrder}
                  disabled={checkoutLoading}
                >
                  {checkoutLoading
                    ? "Processing..."
                    : "Confirm Order"}
                </button>

                <button
                  className="clear"
                  onClick={() => setShowCheckout(false)}
                  disabled={checkoutLoading}
                >
                  Go Back
                </button>
              </>

            )}

          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer>
        cartly.
        <span>React · FastAPI · MongoDB · Cassandra</span>
        © 2026
      </footer>

    </div>
  );
}

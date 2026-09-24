# Flask application factory

`shop.create_app` builds a `Flask` application and registers a blueprint, as Flask
applications usually do. No module calls the factory, since `flask --app shop run` does.
The factory is the root of the automatic `production:flask` world. Flask has no
capability yet, so `@bp.route` is an external registration that protects `index` and what
it calls once `shop.views` is imported. `unused_helper` stays a candidate.

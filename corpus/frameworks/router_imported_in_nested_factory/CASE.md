# A router that the application factory imports in its own body

The service in `services/api` is installed as the distribution of its own directory, so its
package is imported as `chat_api`, not by its path in the repository. `create_app` imports the
`messages` routes module inside its body and includes `messages.router`. That router is
published, so its route and the request model the route takes run. `archive.router` is included
nowhere: its route stays an RCH002 finding.

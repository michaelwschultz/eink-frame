
## Bunch of work done on this in March of 2025


# Basics

- This script currently runs on a Raspberry pi zero w that's connected to the net.
- It fetches a list of frame screens to be displayed via val.town
- That list is then used to fetch the the next image in rotation based on which one is currently
being displayed on the connected eink display derived from state.json.
- You can also tell it which frame to display using the param -F or --frame.
E.G. `python fetch_and_display_image.py --frame weather`


# Add startup process using pm2

pm2 start fetch_and_display_image.py --name fetch_and_display --no-autorestart --cron "0 7,19 * * *"
pm2 save
pm2 startup


pm2 logs fetch_and_display


# More stuff

3D print display&Pi holder 
![3d-model3](https://user-images.githubusercontent.com/85778625/137439738-7db5fb23-6876-4182-80c1-22562b4bd683.JPG)




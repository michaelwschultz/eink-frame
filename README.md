# Add startup process using pm2

pm2 start fetch_and_display_image.py --name fetch_and_display --no-autorestart --cron "0 7,19 * * *"
pm2 save
pm2 startup


pm2 logs fetch_and_display

3D print display&Pi holder 
![3d-model3](https://user-images.githubusercontent.com/85778625/137439738-7db5fb23-6876-4182-80c1-22562b4bd683.JPG)






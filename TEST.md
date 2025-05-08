# auto-reel

Auto-Reel is a lightweight, Python-powered tool that automatically compiles a folder of video clips into a cohesive movie, complete with neatly inserted title cards and hassle-free transcoding—so you can focus on creating content instead of wrestling with manual edits.

It supports:

- GPU
- Chapters
- Source video format conversion
- Per movie configuration from a movie.yaml file

## Code

```bash
clear && task run USE_GPU=true INPUT_DIR=/run/media/emil/MOL/Videos/Sorted OUTPUT_DIR=/run/media/emil/MOL/Videos/Completed-auto-reel YEAR=2017,2018,2019,2020,2021,2022,2023,2024 > output.log 2>&1
clear && task run USE_GPU=true INPUT_DIR=/run/media/emil/MOL/Videos/Sorted OUTPUT_DIR=/run/media/emil/MOL/Videos/Completed-auto-reel YEAR=2023 > output.log 2>&1


clear && task run USE_GPU=false INPUT_DIR=/var/home/emil/Development/larnetio/auto-reel/hack/input OUTPUT_DIR=/var/home/emil/Development/larnetio/auto-reel/hack/output YEAR=2018

clear && task run USE_GPU=false INPUT_DIR=/var/home/emil/Development/larnetio/auto-reel/hack/input OUTPUT_DIR=/var/home/emil/Development/larnetio/auto-reel/hack/output YEAR=2018 -- --dry-run


clear && task run USE_GPU=true INPUT_DIR=/mnt/f/Mormor-och-Lasse_Sorterat OUTPUT_DIR=/mnt/f/Mormor-och-Lasse_Färdigt-movie-merge YEAR=2017,2018,2019,2020,2021,2022,2023,2024
```

```bash
ffmpeg -i ./00400.mp4 \
       -i ./Kubernetes_logo_without_workmark.png \
       -filter_complex "\
         [1:v]scale=-1:300,format=rgba[logo];\
         [0:v][logo]overlay=(W-w)/2:(H-h)/2:enable='between(t,0,7)'[overlaid];\
         [overlaid]fade=out:st=5:d=2[final]" \
       -map "[final]" -map 0:a \
       -c:v libx264 -pix_fmt yuv420p \
       -c:a aac \
       output.mp4
```

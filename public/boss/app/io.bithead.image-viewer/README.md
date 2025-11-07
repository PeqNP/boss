# Image Viewer

The image viewer is designed to show one or more images in a carousel-like view.

## Usage

Use the OS convenience method:

```javascript
let images = ["/img/1.jpg", "/img/2.jpg"];
os.ui.showImageViewer(images);
```

Load the app:

```javascript
let images = ["/img/1.jpg", "/img/2.jpg"];
let app = await os.openApplication("io.bithead.image-viewer");
let win = await app.loadController("ImageViewer");
win.ui.show(function(ctrl) {
    ctrl.configure(imgs);
});
```

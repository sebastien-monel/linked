if (Notification.permission == "denied") {
  Notification.requestPermission(location.reload(true))
} else {
  const notification = new Notification("Hi there!");
}

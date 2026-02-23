//if (Notification?.permission !== "denied")
//{
  if (Notification.permission == "default") {
    Notification.requestPermission(location.reload(true))
  } else {
    const notification = new Notification("Hi there!");
  }
//}

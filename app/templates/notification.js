Notification.requestPermission().then((status) => {
  //if (status === "denied") {
  //}
  
  //if (status === "default") {
    //Notification.requestPermission(location.reload(true))
  //} 
  
  if (status === "granted") {
    const interval = setInterval(() => {
      const notification = new Notification("Brouillon :", {body: "Hi there !!!"} );
    }, 10000)
  }
})

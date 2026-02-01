function getURLParameter(sParam) {
    const params = new URLSearchParams(window.location.search)
    return params.get(sParam)
}

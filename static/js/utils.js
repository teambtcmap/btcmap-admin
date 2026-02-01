 /**
  * Passing the name of URL parameter we get its value  
  * @param {string} sParam - The search string also known as URL parameter 
  * @returns {string} - The URL parameter content
  * @throws {} 
  */
function getURLParameter(sParam) {
    const params = new URLSearchParams(window.location.search)
    return params.get(sParam)
}
 /**
  * Passing a text without formatation, this text is normalized to get its main data  
  * @param {string} text - Unformated text 
  * @returns {string} - Formatted text 
  * @throws {} 
  */
function cleanIssueText(text) {
    return text?.replace(/\n/g, ' ').trim() || ''
}

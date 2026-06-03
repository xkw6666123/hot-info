(function(){
  var t = document.body.innerText;
  var lines = t.split(String.fromCharCode(10)).filter(function(l){
    l = l.trim();
    if (l.length < 8) return false;
    if (/^(登录|注册|下载|打开|看更多|收藏|分享|评论|点赞|关注|粉丝|获赞|首页|推荐)/.test(l)) return false;
    if (/ICP备|公安网箤|经营许可证|网络文化/.test(l)) return false;
    return true;
  });
  return lines.slice(0, 15).join(String.fromCharCode(10)).substring(0, 2000);
})()
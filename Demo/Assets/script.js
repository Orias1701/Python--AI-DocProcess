document.addEventListener("DOMContentLoaded", () => {
    // --- Cấu hình API (Giữ nguyên) ---
    const API_TOKEN = ""; // Điền token của bạn vào đây
    const API_BASE_URL = "http://127.0.0.1:8000";

    // --- Lấy các phần tử layout MỚI ---
    const appContainer = document.getElementById("appContainer");
    const chatBody = document.getElementById("chatBody");
    const chatForm = document.getElementById("chatForm");
    const textInput = document.getElementById("textInput");
    const sendBtn = chatForm.querySelector(".send-btn");
    
    // --- Lấy các phần tử file (Giữ nguyên) ---
    const fileInput = document.getElementById("fileUpload");
    const fileCard = document.getElementById("fileCard");
    const fileNameSpan = document.getElementById("fileName");
    const removeFileBtn = document.getElementById("removeFile");

    // --- Biến trạng thái ---
    let chatIsActive = false;

    // --- HÀM KÍCH HOẠT LAYOUT CHAT ---
    function activateChatLayout() {
        if (!chatIsActive) {
            appContainer.classList.remove("layout-centered");
            appContainer.classList.add("layout-active");
            chatIsActive = true;
        }
    }

    // --- HÀM HIỂN THỊ NÚT GỬI ---
    textInput.addEventListener("input", () => {
        if (textInput.value.trim().length > 0) {
            sendBtn.style.display = "flex";
        } else {
            sendBtn.style.display = "none";
        }

        textInput.style.height = 'auto';
        textInput.style.height = (textInput.scrollHeight) + 'px';
    });

    // --- CÁC HÀM XỬ LÝ CHAT ---

    function typeWriter(element, text, delay = 10) {
        let i = 0;
        element.innerHTML = ""; 
        
        function typing() {
            if (i < text.length) {
                if (text.substring(i, i + 2) === "**") {
                    let boldEnd = text.indexOf("**", i + 2);
                    if (boldEnd !== -1) {
                        element.innerHTML += `<strong>${text.substring(i + 2, boldEnd)}</strong>`;
                        i = boldEnd + 2;
                    } else {
                        element.innerHTML += text.substring(i, i+2); i += 2;
                    }
                } else if (text.substring(i, i + 1) === "\n") {
                    element.innerHTML += "<br>"; i++;
                }
                else {
                    element.innerHTML += text.charAt(i); i++;
                }
                chatBody.scrollTop = chatBody.scrollHeight;
                setTimeout(typing, delay);
            }
        }
        typing();
    }

    function appendMessage(sender, text, useTypewriter = false) {
        // Tự động kích hoạt layout chat khi có tin nhắn
        activateChatLayout();

        const messageRow = document.createElement("div");
        const avatar = document.createElement("div");
        const messageBubble = document.createElement("div");

        messageRow.classList.add("message-row", `${sender}-row`);
        avatar.classList.add("avatar");
        messageBubble.classList.add(sender === 'bot' ? "bot-msg" : "user-msg");

        if (sender === 'bot' && useTypewriter) {
            typeWriter(messageBubble, text, 5);
        } else {
            const formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
            messageBubble.innerHTML = formattedText;
        }

        messageRow.appendChild(avatar);
        messageRow.appendChild(messageBubble);
        chatBody.appendChild(messageRow);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function appendTyping() {
        activateChatLayout(); // Kích hoạt layout
        const typing = document.createElement("div");
        typing.classList.add("typing");
        typing.textContent = "AI đang xử lý...";
        chatBody.appendChild(typing);
        chatBody.scrollTop = chatBody.scrollHeight;
        return typing;
    }

    // --- CÁC HÀM XỬ LÝ FILE (Giữ nguyên) ---

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (file) {
            fileCard.style.display = "flex";
            fileNameSpan.textContent = file.name;
        } else {
            fileCard.style.display = "none";
        }
    });

    removeFileBtn.addEventListener("click", () => {
        fileInput.value = "";
        fileCard.style.display = "none";
    });

    // --- CÁC HÀM GỌI API (Giữ nguyên, nhưng thêm 'activateChatLayout') ---

    async function sendQuery(query) {
        activateChatLayout(); // Kích hoạt layout
        appendMessage("user", query);
        const typing = appendTyping();

        const headers = { "Content-Type": "application/json" };
        if (API_TOKEN) {
            headers["Authorization"] = `Bearer ${API_TOKEN}`;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/search`, {
                method: "POST",
                headers: headers,
                body: JSON.stringify({ query: query, k: 1 }) 
            });
            
            const data = await response.json();
            typing.remove();

            if (response.ok) {
                let formattedResponse = "✨**Kết quả tìm kiếm:**\n";
                if (data.length > 0) {
                    data.forEach((item, index) => {
                        formattedResponse += `\n--- **Kết quả ${index + 1}** ---\n`;
                        const fields = item.fields;
                        if (fields) {
                            let contentFound = false;
                            if (fields.Article) {
                                formattedResponse += fields.Article + "\n";
                                contentFound = true;
                            }
                            if (fields.Content && Array.isArray(fields.Content)) {
                                formattedResponse += fields.Content.join("\n");
                                contentFound = true;
                            }
                            if (!contentFound) {
                                formattedResponse += "(Không tìm thấy nội dung 'Article' hoặc 'Content')";
                            }
                        } else {
                            formattedResponse += " - (Không có dữ liệu 'fields')\n";
                        }
                    });
                } else {
                    formattedResponse += "Không tìm thấy kết quả nào phù hợp.";
                }
                appendMessage("bot", formattedResponse, true);
            } else {
                appendMessage("bot", `❌ **Lỗi:** ${data.detail || "Không rõ"}`, true);
            }
        } catch (err) {
            typing.remove();
            appendMessage("bot", "⚠️ **Lỗi kết nối:** Không thể kết nối tới API!", true);
        }
    }

    async function sendFile(file) {
        activateChatLayout(); // Kích hoạt layout
        appendMessage("user", `Đã đính kèm: ${file.name}`);
        const typing = appendTyping();
        const formData = new FormData();
        formData.append("file", file);

        const headers = {};
        if (API_TOKEN) {
            headers["Authorization"] = `Bearer ${API_TOKEN}`;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/process_pdf`, {
                method: "POST",
                headers: headers,
                body: formData
            });
            const data = await response.json();
            typing.remove();

            if (response.ok && data.status === "success") {
                if (data.checkstatus === "ok") {
                    appendMessage("bot", `✨**Phân tích PDF thành công!**\nChủ đề: **${data.category}**.\n\n**Tóm tắt:**\n${data.summary}`, true);
                } else {
                    appendMessage("bot", `⚠️**Không thể xử lý PDF**\nLý do: ${data.category}`, true);
                }  
            } else {
                appendMessage("bot", `❌ **Lỗi:** ${data.detail || "Không rõ"}`, true);
            }
        } catch (err) {
            typing.remove();
            appendMessage("bot", "⚠️ **Lỗi kết nối:** Không thể kết nối tới API!", true);
        }
    }

    // --- HÀM SUBMIT FORM CHÍNH ---
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        sendBtn.disabled = true;

        const file = fileInput.files[0];
        const query = textInput.value.trim();

        // 🔹 Xoá input NGAY khi người dùng nhấn gửi
        textInput.value = "";
        requestAnimationFrame(() => {
            textInput.style.height = 'auto';
        });
        sendBtn.style.display = 'none';

        try {
            if (file) {
                await sendFile(file);
                fileInput.value = "";
                fileCard.style.display = "none";
            } else if (query) {
                await sendQuery(query);
            } else {
                return;
            }
        } finally {
            sendBtn.disabled = false;
        }
    });

    // Cho phép gửi bằng Enter (và Shift+Enter để xuống dòng)
    textInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.requestSubmit();
        }
    });

});
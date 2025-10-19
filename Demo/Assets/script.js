document.addEventListener("DOMContentLoaded", () => {
    const chatBody = document.getElementById("chatBody");
    const chatForm = document.getElementById("chatForm");
    const fileInput = document.getElementById("fileUpload");
    const fileCard = document.getElementById("fileCard");
    const fileNameSpan = document.getElementById("fileName");
    const removeFileBtn = document.getElementById("removeFile");

    /**
     * Gõ từng ký tự của một chuỗi văn bản vào một phần tử.
     * @param {HTMLElement} element - Phần tử để gõ chữ vào.
     * @param {string} text - Nội dung văn bản.
     * @param {number} delay - Thời gian trễ giữa các ký tự (ms).
     */
    function typeWriter(element, text, delay = 10) {
        let i = 0;
        element.innerHTML = ""; // Xóa nội dung cũ
        
        function typing() {
            if (i < text.length) {
                // Giữ lại các thẻ HTML như **, \n
                if (text.substring(i, i + 2) === "**") {
                    let boldEnd = text.indexOf("**", i + 2);
                    if (boldEnd !== -1) {
                        element.innerHTML += `<strong>${text.substring(i + 2, boldEnd)}</strong>`;
                        i = boldEnd + 2;
                    }
                } else if (text.substring(i, i + 1) === "\n") {
                     element.innerHTML += "<br>";
                     i++;
                }
                else {
                    element.innerHTML += text.charAt(i);
                    i++;
                }
                chatBody.scrollTop = chatBody.scrollHeight; // Cuộn xuống khi gõ
                setTimeout(typing, delay);
            }
        }
        typing();
    }


    /**
     * Tạo và nối một hàng tin nhắn mới vào thân chat.
     * @param {string} sender - "user" hoặc "bot".
     * @param {string} text - Nội dung văn bản của tin nhắn.
     * @param {boolean} useTypewriter - Kích hoạt hiệu ứng gõ chữ cho bot.
     */
    function appendMessage(sender, text, useTypewriter = false) {
        const messageRow = document.createElement("div");
        const avatar = document.createElement("div");
        const messageBubble = document.createElement("div")

        messageRow.classList.add("message-row", `${sender}-row`);
        avatar.classList.add("avatar");
        avatar.textContent = "";
        if (sender === 'bot'){
            messageBubble.classList.add("bot-msg");
        } else {
            messageBubble.classList.add("user-msg");
        }

        if (sender === 'bot' && useTypewriter) {
            typeWriter(messageBubble, text, 5);
        } else {
            // Thay thế markdown đơn giản cho hiển thị
            const formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
            messageBubble.innerHTML = formattedText;
        }

        messageRow.appendChild(avatar);
        messageRow.appendChild(messageBubble);
        chatBody.appendChild(messageRow);
        chatBody.scrollTop = chatBody.scrollHeight;
    }


    /**
     * Hiển thị chỉ báo đang gõ của bot.
     */
    function appendTyping() {
        const typing = document.createElement("div");
        typing.classList.add("typing");
        typing.textContent = "AI đang xử lý...";
        chatBody.appendChild(typing);
        chatBody.scrollTop = chatBody.scrollHeight;
        return typing;
    }

    // Chào mừng ban đầu
    setTimeout(() => {
        appendMessage("bot", "Xin chào! Hãy tải lên file PDF để tôi tóm tắt và phân loại cho bạn.", true);
    }, 500);


    // Khi chọn file, hiển thị card tên
    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (file) {
            fileCard.style.display = "flex";
            fileNameSpan.textContent = file.name;
        } else {
            fileCard.style.display = "none";
        }
    });

    // Nút xóa file
    removeFileBtn.addEventListener("click", () => {
        fileInput.value = "";
        fileCard.style.display = "none";
    });

    /**
     * Gửi file đến backend API để xử lý.
     * @param {File} file - File PDF cần gửi.
     */
    async function sendFile(file) {
        appendMessage("user", `Attached: ${file.name}`);

        const typing = appendTyping();
        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("http://127.0.0.1:8000/process_pdf", {
                method: "POST",
                body: formData
            });
            const data = await response.json();
            typing.remove();

            if (response.ok && data.status === "success") {
                if (data.checkstatus === "accept") {
                    appendMessage("bot", `✨**Chatbot**\n Đây là một văn bản về chủ đề **${data.category}** với nội dung được tóm tắt như sau: \n${data.summary}`, true);
                } else {
                    appendMessage("bot", `✨**Chatbot**\n Văn bản không được chấp nhận:\n${data.summary}`, true);
                }  
            } else {
                appendMessage("bot", `❌ **Lỗi:** ${data.message || "Không rõ"}`, true);
            }
        } catch (err) {
            typing.remove();
            appendMessage("bot", "⚠️ **Lỗi kết nối:** Không thể kết nối tới API!", true);
        }
    }

    // Xử lý việc gửi form
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = fileInput.files[0];
        if (!file) {
            appendMessage("bot", "📄 Vui lòng chọn một file PDF để xử lý.", true);
            return;
        }
        await sendFile(file);
        fileInput.value = "";
        fileCard.style.display = "none";
    });
});
(function () {
    function parseJsonScript(id, fallback) {
        var node = document.getElementById(id);
        if (!node) {
            return fallback;
        }
        try {
            return JSON.parse(node.textContent || '');
        } catch (error) {
            return fallback;
        }
    }

    function getHomeV2Config() {
        return parseJsonScript('home-v2-frontend-config', {}) || {};
    }

    function getCsrfToken() {
        var field = document.querySelector('[name=csrfmiddlewaretoken]');
        if (field && field.value) {
            return field.value;
        }
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function showFeedback(message, type) {
        if (window.showToast) {
            window.showToast(message, type || 'info');
            return;
        }
        if ((type || 'info') === 'error') {
            alert(message);
        }
    }

    function launchCard(card) {
        var href = card.dataset.launchHref || (card.dataset.productId ? '/products/' + card.dataset.productId + '/' : '');
        if (!href) {
            return;
        }
        if (card.dataset.launchExternal === 'true') {
            window.open(href, '_blank', 'noopener');
            return;
        }
        window.location.href = href;
    }

    function initHomeV2Interactions() {
        var config = getHomeV2Config();
        var favoriteIds = new Set();
        var favoriteData = parseJsonScript('home-favorite-ids-data', []);
        if (Array.isArray(favoriteData)) {
            favoriteData.forEach(function (value) {
                var parsed = parseInt(value, 10);
                if (!Number.isNaN(parsed)) {
                    favoriteIds.add(parsed);
                }
            });
        }

        function updateFavoriteButtonState(button, isFavorite) {
            if (!button) {
                return;
            }
            button.setAttribute('aria-pressed', isFavorite ? 'true' : 'false');
            button.classList.toggle('border-amber-300', isFavorite);
            button.classList.toggle('text-amber-500', isFavorite);
            button.classList.toggle('bg-amber-50', isFavorite);
            button.classList.toggle('border-slate-200', !isFavorite);
            button.classList.toggle('text-slate-300', !isFavorite);
            button.classList.toggle('bg-white', !isFavorite);
            button.title = isFavorite ? '즐겨찾기 해제' : '즐겨찾기';
        }

        function syncFavoriteButtons() {
            document.querySelectorAll('[data-favorite-toggle="true"]').forEach(function (button) {
                var pid = parseInt(button.dataset.productId || '', 10);
                var isFavorite = !Number.isNaN(pid) && favoriteIds.has(pid);
                updateFavoriteButtonState(button, isFavorite);
            });
        }

        document.querySelectorAll('.product-card').forEach(function (card) {
            card.addEventListener('click', function (event) {
                if (event.target.closest('[data-favorite-toggle="true"]')) {
                    return;
                }
                launchCard(card);
            });
            card.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    launchCard(card);
                }
            });
        });

        document.querySelectorAll('[data-favorite-toggle="true"]').forEach(function (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();

                var pid = parseInt(this.dataset.productId || '', 10);
                if (Number.isNaN(pid) || !config.toggleFavoriteUrl) {
                    return;
                }

                var csrfToken = getCsrfToken();
                if (!csrfToken) {
                    showFeedback('보안 토큰을 확인할 수 없습니다. 새로고침 후 다시 시도해 주세요.', 'error');
                    return;
                }

                fetch(config.toggleFavoriteUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({ product_id: pid }),
                })
                    .then(function (response) {
                        return response.json().catch(function () { return {}; }).then(function (payload) {
                            if (!response.ok || payload.status !== 'ok') {
                                throw new Error(payload.error || '즐겨찾기 처리에 실패했습니다.');
                            }
                            return payload;
                        });
                    })
                    .then(function (payload) {
                        if (payload.is_favorite) {
                            favoriteIds.add(pid);
                            showFeedback('즐겨찾기에 추가했습니다.', 'success');
                        } else {
                            favoriteIds.delete(pid);
                            showFeedback('즐겨찾기에서 제거했습니다.', 'success');
                        }
                        syncFavoriteButtons();
                    })
                    .catch(function (error) {
                        showFeedback(error.message || '즐겨찾기 처리 중 오류가 발생했습니다.', 'error');
                    });
            });
        });

        document.addEventListener('click', function (event) {
            var element = event.target.closest('[data-track]');
            if (!element) {
                return;
            }
            var productId = element.dataset.productId || (element.closest('[data-product-id]') || {}).dataset?.productId;
            if (!productId || !config.trackUsageUrl) {
                return;
            }
            var token = getCsrfToken();
            if (!token) {
                return;
            }
            var sourceMap = {
                quick_action: 'home_quick',
                mini_card: 'home_section',
                mini_app_open: 'home_mini',
                game_card: 'home_game',
                game_banner: 'home_game',
                section_more_toggle: 'home_section',
            };
            fetch(config.trackUsageUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': token,
                },
                body: JSON.stringify({
                    product_id: parseInt(productId, 10),
                    action: 'launch',
                    source: sourceMap[element.dataset.track] || 'other',
                }),
            })
                .then(function (response) {
                    if (!response.ok) {
                        showFeedback('사용 기록 저장에 실패했습니다.', 'error');
                    }
                })
                .catch(function () {
                    showFeedback('사용 기록 저장 중 네트워크 오류가 발생했습니다.', 'error');
                });
        });

        syncFavoriteButtons();
    }

    window.homeCalendarWidget = function () {
        var config = getHomeV2Config();
        var calendarConfig = config.calendar || {};
        return {
            currentDate: new Date(),
            events: [],
            createModalOpen: false,
            todayMemoModalOpen: false,
            todayMemoReturnFocusElement: null,
            selectedDateKey: '',
            selectedDateLabel: '',
            selectedDateEvents: [],
            selectedDateIsEmpty: true,
            isSubmitting: false,
            createContextDateText: '',
            refreshTicker: null,
            createForm: {
                title: '',
                note: '',
                start_time: '',
                end_time: '',
                is_all_day: false,
                color: 'indigo',
            },

            init: function () {
                this.syncSelectedDate(new Date());
                this.refreshEvents();
                this.refreshTicker = setInterval(() => this.refreshEvents(), 120000);
                window.addEventListener('focus', () => this.refreshEvents());
            },

            refreshEvents: async function () {
                if (!calendarConfig.eventsUrl) {
                    return;
                }
                try {
                    var payload = await this.requestJson(calendarConfig.eventsUrl);
                    this.events = (payload.events || []).map((event) => this.normalizeEvent(event));
                    this.syncSelectedDate(this.selectedDateKey ? this.parseDateKey(this.selectedDateKey) : new Date());
                } catch (error) {
                    showFeedback('홈 캘린더를 불러오지 못했습니다.', 'error');
                }
            },

            normalizeEvent: function (event) {
                return {
                    ...event,
                    title: event.title || '일정',
                    color: event.color || 'indigo',
                    is_all_day: !!event.is_all_day,
                    start_time: new Date(event.start_time),
                    end_time: new Date(event.end_time),
                };
            },

            getCsrfToken: getCsrfToken,

            requestJson: async function (url, options) {
                var response = await fetch(url, options || {});
                var payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    var error = new Error(payload.message || '요청 처리에 실패했습니다.');
                    error.payload = payload;
                    throw error;
                }
                return payload;
            },

            pad: function (value) {
                return String(value).padStart(2, '0');
            },

            dateKey: function (dateValue) {
                var date = new Date(dateValue);
                return date.getFullYear() + '-' + this.pad(date.getMonth() + 1) + '-' + this.pad(date.getDate());
            },

            parseDateKey: function (dateStr) {
                var parts = dateStr.split('-').map(Number);
                return new Date(parts[0], parts[1] - 1, parts[2]);
            },

            toDatetimeLocal: function (dateValue) {
                var date = new Date(dateValue);
                return date.getFullYear() + '-' + this.pad(date.getMonth() + 1) + '-' + this.pad(date.getDate()) + 'T' + this.pad(date.getHours()) + ':' + this.pad(date.getMinutes());
            },

            get currentMonthText() {
                return this.currentDate.getFullYear() + '년 ' + (this.currentDate.getMonth() + 1) + '월';
            },

            get todayEventsCount() {
                return this.events.filter((event) => this.dateKey(event.start_time) === this.dateKey(new Date())).length;
            },

            get weekEventsCount() {
                var now = new Date();
                var start = new Date(now);
                var mondayOffset = (now.getDay() + 6) % 7;
                start.setDate(now.getDate() - mondayOffset);
                start.setHours(0, 0, 0, 0);
                var end = new Date(start);
                end.setDate(start.getDate() + 7);
                return this.events.filter((event) => event.start_time >= start && event.start_time < end).length;
            },

            get calendarDates() {
                var year = this.currentDate.getFullYear();
                var month = this.currentDate.getMonth();
                var first = new Date(year, month, 1);
                var last = new Date(year, month + 1, 0);
                var start = new Date(first);
                start.setDate(start.getDate() - start.getDay());
                var end = new Date(last);
                if (end.getDay() !== 6) {
                    end.setDate(end.getDate() + (6 - end.getDay()));
                }
                var dates = [];
                for (var cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
                    dates.push(new Date(cursor));
                }
                return dates;
            },

            prevMonth: function () {
                this.currentDate = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() - 1, 1);
            },

            nextMonth: function () {
                this.currentDate = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 1);
            },

            isCurrentMonth: function (date) {
                return date.getMonth() === this.currentDate.getMonth() && date.getFullYear() === this.currentDate.getFullYear();
            },

            isToday: function (date) {
                var today = new Date();
                return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear();
            },

            isSelected: function (date) {
                return this.selectedDateKey === this.dateKey(date);
            },

            getEventsForDate: function (date) {
                return this.events
                    .filter((event) => this.dateKey(event.start_time) === this.dateKey(date))
                    .sort((left, right) => left.start_time - right.start_time);
            },

            getVisibleEventsForDate: function (date) {
                return this.getEventsForDate(date).slice(0, 1);
            },

            getOverflowCountForDate: function (date) {
                var total = this.getEventsForDate(date).length;
                return total > 1 ? total - 1 : 0;
            },

            formatEventTimeShort: function (dateValue, isAllDay) {
                if (isAllDay) {
                    return '종일';
                }
                var date = new Date(dateValue);
                return this.pad(date.getHours()) + ':' + this.pad(date.getMinutes());
            },

            eventLabel: function (event) {
                var title = event.title || '일정';
                return this.formatEventTimeShort(event.start_time, event.is_all_day) + ' ' + title;
            },

            dayTooltip: function (date) {
                var dateText = this.formatAgendaDate(this.dateKey(date));
                var events = this.getEventsForDate(date);
                if (!events.length) {
                    return dateText + ' 일정 추가';
                }
                return dateText + ' 일정 ' + events.length + '건 보기';
            },

            eventChipClass: function (event) {
                var map = {
                    indigo: 'bg-indigo-50 border-indigo-200 text-indigo-700',
                    rose: 'bg-rose-50 border-rose-200 text-rose-700',
                    amber: 'bg-amber-50 border-amber-200 text-amber-700',
                    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
                    sky: 'bg-sky-50 border-sky-200 text-sky-700',
                };
                return map[event.color] || map.indigo;
            },

            formatAgendaDate: function (dateStr) {
                var date = this.parseDateKey(dateStr);
                var days = ['일', '월', '화', '수', '목', '금', '토'];
                return (date.getMonth() + 1) + '월 ' + date.getDate() + '일 (' + days[date.getDay()] + ')';
            },

            formatClock: function (dateValue) {
                var date = new Date(dateValue);
                return this.pad(date.getHours()) + ':' + this.pad(date.getMinutes());
            },

            formatEventRange: function (event) {
                if (!event) {
                    return '';
                }
                var start = new Date(event.start_time);
                var end = new Date(event.end_time);
                if (event.is_all_day) {
                    return this.formatAgendaDate(this.dateKey(start)) + ' · 하루 종일';
                }
                if (this.dateKey(start) === this.dateKey(end)) {
                    return this.formatAgendaDate(this.dateKey(start)) + ' · ' + this.formatClock(start) + ' - ' + this.formatClock(end);
                }
                return this.formatAgendaDate(this.dateKey(start)) + ' ' + this.formatClock(start) + ' ~ ' + this.formatAgendaDate(this.dateKey(end)) + ' ' + this.formatClock(end);
            },

            syncSelectedDate: function (date) {
                var selectedDate = new Date(date);
                var key = this.dateKey(selectedDate);
                this.selectedDateKey = key;
                this.selectedDateLabel = this.formatAgendaDate(key);
                this.selectedDateEvents = this.getEventsForDate(selectedDate);
                this.selectedDateIsEmpty = this.selectedDateEvents.length === 0;
            },

            handleDateClick: function (date) {
                this.syncSelectedDate(date);
            },

            openTodayMemoModal: function (event) {
                this.todayMemoReturnFocusElement = event && event.currentTarget ? event.currentTarget : document.activeElement;
                this.todayMemoModalOpen = true;
            },

            closeTodayMemoModal: function () {
                this.todayMemoModalOpen = false;
                if (this.todayMemoReturnFocusElement && typeof this.todayMemoReturnFocusElement.focus === 'function') {
                    window.setTimeout(() => this.todayMemoReturnFocusElement.focus(), 0);
                }
            },

            openCreateModalForSelectedDate: function () {
                if (!this.selectedDateKey) {
                    this.openCreateModalForDate(new Date());
                    return;
                }
                this.openCreateModalForDate(this.parseDateKey(this.selectedDateKey));
            },

            openCreateModalForDate: function (date) {
                var baseDate = new Date(date);
                this.syncSelectedDate(baseDate);
                var start = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate(), 9, 0, 0, 0);
                var end = new Date(start);
                end.setHours(start.getHours() + 1, 0, 0, 0);
                this.createContextDateText = this.formatAgendaDate(this.dateKey(start));
                this.createForm = {
                    title: '',
                    note: '',
                    start_time: this.toDatetimeLocal(start),
                    end_time: this.toDatetimeLocal(end),
                    is_all_day: false,
                    color: 'indigo',
                };
                this.createModalOpen = true;
            },

            submitCreateEvent: async function () {
                if (!calendarConfig.createEventUrl) {
                    return;
                }
                this.isSubmitting = true;
                var body = new URLSearchParams();
                body.set('title', this.createForm.title);
                body.set('note', this.createForm.note || '');
                body.set('start_time', this.createForm.start_time);
                body.set('end_time', this.createForm.end_time);
                body.set('color', this.createForm.color);
                if (this.createForm.is_all_day) {
                    body.set('is_all_day', 'on');
                }
                try {
                    await this.requestJson(calendarConfig.createEventUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                            'X-CSRFToken': this.getCsrfToken(),
                        },
                        body: body.toString(),
                    });
                    this.createModalOpen = false;
                    await this.refreshEvents();
                    showFeedback('일정을 저장했습니다.', 'success');
                } catch (error) {
                    var isValidationError = error.payload && error.payload.code === 'validation_error';
                    var message = isValidationError
                        ? '입력값을 확인해 주세요. 종료 시간은 시작 시간 이후여야 합니다.'
                        : (error.message || '일정 저장에 실패했습니다.');
                    showFeedback(message, 'error');
                } finally {
                    this.isSubmitting = false;
                }
            },
        };
    };

    document.addEventListener('DOMContentLoaded', initHomeV2Interactions);
})();
